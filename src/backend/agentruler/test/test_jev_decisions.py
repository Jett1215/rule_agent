import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from loguru import logger

from agentruler.schemas.common import JevConfig
from agentruler.services.decision.jev import JevDecisionService
from agentruler.settings import app_settings, init_app_settings


def tools(count):
    return [SimpleNamespace(name=f"tool_{i}", description=f"工具 {i}") for i in range(count)]


class JevDecisionTests(unittest.IsolatedAsyncioTestCase):
    def service(self, probabilities=None, **overrides):
        config = JevConfig(
            **{"mode": "enforce", "api_key": "test-secret", **overrides}
        )
        self.requests = []

        def respond(request):
            body = json.loads(request.content)
            self.requests.append((request, body))
            values = probabilities or {"needs_tools": 0.01}
            return httpx.Response(200, json={
                "model": "jev-1.13.0",
                "answers": {key: {"type": "noul", "noul": value} for key, value in values.items()},
                "usage": {"input_tokens": 150, "output_tokens": 4},
            })

        return JevDecisionService(config, transport=httpx.MockTransport(respond))

    async def test_gate_only_skips_confident_no_in_enforce_mode(self):
        for probability, should_run in [(0, False), (0.05, False), (0.051, True), (0.5, True), (1, True)]:
            with self.subTest(probability=probability):
                service = self.service({"needs_tools": probability})
                result = await service.should_run_tools([{"role": "user", "content": "你好"}], tools(1))
                self.assertEqual(result, should_run)

    async def test_observe_records_decisions_without_applying_either_optimization(self):
        service = self.service({"needs_tools": 0.01}, mode="observe")
        self.assertTrue(await service.should_run_tools([], tools(1)))
        self.assertEqual(len(self.requests), 1)

        service = self.service(
            {"relevant_0": 0.99, "relevant_1": 0.01},
            mode="observe", min_tools_for_selection=2, max_selected_tools=1,
        )
        self.assertIsNone(await service.select_tools([], tools(2)))
        self.assertEqual(len(self.requests), 1)

    async def test_disabled_missing_key_and_individual_switches_do_not_call_provider(self):
        for overrides in [{"mode": "disabled"}, {"api_key": ""}, {"tool_gate_enabled": False}]:
            with self.subTest(overrides=overrides):
                service = self.service(**overrides)
                self.assertTrue(await service.should_run_tools([], tools(1)))
                self.assertEqual(self.requests, [])
        service = self.service(tool_selector_enabled=False, min_tools_for_selection=2, max_selected_tools=1)
        self.assertIsNone(await service.select_tools([], tools(2)))
        self.assertEqual(self.requests, [])

    async def test_no_tools_and_small_rosters_do_not_call_provider(self):
        service = self.service()
        self.assertFalse(await service.should_run_tools([], []))
        self.assertIsNone(await service.select_tools([], tools(3)))
        self.assertEqual(self.requests, [])

    async def test_request_preserves_history_and_tool_results_but_omits_argument_values(self):
        service = self.service()
        messages = [
            {"role": "system", "content": "历史：用户要求查询杭州天气"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"name": "weather", "args": {"api_key": "do-not-send-this-argument"}},
            ]},
            {"role": "tool", "content": "今天晴天"},
            {"role": "user", "content": "明天呢？"},
        ]
        await service.should_run_tools(messages, tools(1))

        request, body = self.requests[0]
        self.assertEqual(str(request.url), "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(request.headers["Authorization"], "Bearer test-secret")
        self.assertEqual(body["model"], "jev-1.13.0")
        self.assertEqual(body["state"]["messages"][0]["content"], messages[0]["content"])
        self.assertEqual(body["state"]["messages"][-1]["content"], "明天呢？")
        self.assertEqual(body["state"]["messages"][1]["tool_names"], ["weather"])
        self.assertNotIn("do-not-send-this-argument", request.content.decode())
        self.assertEqual(body["questions"]["needs_tools"]["type"], "noul")

    async def test_large_or_non_text_context_falls_back_without_silent_truncation(self):
        for content in ["超长" * 100, [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}]]:
            service = self.service(max_context_chars=100)
            self.assertTrue(await service.should_run_tools([{"role": "user", "content": content}], tools(1)))
            self.assertIsNone(await service.select_tools(
                [{"role": "user", "content": content}], tools(10),
            ))
            self.assertEqual(self.requests, [])
        service = self.service(max_tools=1)
        self.assertTrue(await service.should_run_tools([], tools(2)))
        self.assertEqual(self.requests, [])

    async def test_selector_preserves_multiple_plausible_tools_and_original_order(self):
        service = self.service(
            {"relevant_0": 0.2, "relevant_1": 0.99, "relevant_2": 0.01},
            min_tools_for_selection=3, max_selected_tools=2,
        )
        candidates = tools(3)
        selected = await service.select_tools([], candidates)
        self.assertEqual(selected, candidates[:2])
        self.assertIs(selected[0], candidates[0])
        self.assertEqual(len(self.requests[0][1]["questions"]), 3)

    async def test_uncertain_and_too_many_relevant_tools_keep_full_roster(self):
        for values in [
            {"relevant_0": 0.5, "relevant_1": 0.1},
            {"relevant_0": 0.99, "relevant_1": 0.95},
            {"relevant_0": 0.01, "relevant_1": 0.01},
        ]:
            service = self.service(values, min_tools_for_selection=2, max_selected_tools=1)
            self.assertIsNone(await service.select_tools([], tools(2)))

    async def test_http_errors_and_timeout_fall_back_without_retries(self):
        for status in [401, 429, 500]:
            service = self.service()
            calls = []

            def fail(request):
                calls.append(request)
                return httpx.Response(status, json={"error": "provider-details"})

            service._transport = httpx.MockTransport(fail)
            self.assertTrue(await service.should_run_tools([], tools(1)))
            self.assertEqual(len(calls), 1)

        async def slow(request):
            await asyncio.sleep(0.1)
            raise AssertionError("The whole-request deadline must cancel this request")

        service = self.service(timeout_seconds=0.01)
        service._transport = httpx.MockTransport(slow)
        self.assertTrue(await service.should_run_tools([], tools(1)))

    async def test_missing_wrong_type_and_invalid_probabilities_fall_back(self):
        bad_answers = [
            {},
            {"needs_tools": {"type": "choice", "noul": 0.01}},
            {"needs_tools": {"type": "noul", "noul": True}},
            {"needs_tools": {"type": "noul", "noul": "0.01"}},
            {"needs_tools": {"type": "noul", "noul": -0.1}},
            {"needs_tools": {"type": "noul", "noul": 1.1}},
            {"needs_tools": {"type": "noul", "noul": float("nan")}},
        ]
        for answers in bad_answers:
            service = self.service()
            service._transport = httpx.MockTransport(lambda request: httpx.Response(
                200, content=json.dumps({"answers": answers}),
                headers={"Content-Type": "application/json"},
            ))
            self.assertTrue(await service.should_run_tools([], tools(1)))

    async def test_cancelled_request_propagates_instead_of_launching_original_agent(self):
        async def cancel(request):
            raise asyncio.CancelledError()

        service = self.service()
        service._transport = httpx.MockTransport(cancel)
        with self.assertRaises(asyncio.CancelledError):
            await service.should_run_tools([], tools(1))

    async def test_usage_is_recorded_with_request_user_and_actual_model(self):
        service = self.service()
        save = AsyncMock()
        fake_module = SimpleNamespace(UsageStatsService=SimpleNamespace(create_usage_stats=save))
        with (
            patch("agentruler.services.decision.jev.get_user_id_context", return_value="test-user"),
            patch("agentruler.services.decision.jev.get_agent_name_context", return_value="test-agent"),
            patch.dict("sys.modules", {"agentruler.api.services.usage_stats": fake_module}),
        ):
            self.assertFalse(await service.should_run_tools([], tools(1)))
        save.assert_awaited_once_with(
            agent="test-agent", model="jev-1.13.0", user_id="test-user",
            input_tokens=150, output_tokens=4,
        )

    async def test_slow_usage_database_does_not_block_a_successful_decision(self):
        async def blocked(**kwargs):
            await asyncio.Event().wait()

        service = self.service()
        save = AsyncMock(side_effect=blocked)
        fake_module = SimpleNamespace(UsageStatsService=SimpleNamespace(create_usage_stats=save))
        with (
            patch("agentruler.services.decision.jev.get_user_id_context", return_value="test-user"),
            patch.dict("sys.modules", {"agentruler.api.services.usage_stats": fake_module}),
        ):
            result = await asyncio.wait_for(service.should_run_tools([], tools(1)), timeout=1)
        self.assertFalse(result)
        save.assert_awaited_once()

    async def test_optional_configuration_loads_through_existing_yaml_loader(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(app_settings, "jev", {}),
            patch.dict(os.environ, {"JEV_MODE": ""}),
        ):
            path = Path(directory) / "settings.yaml"
            path.write_text("jev:\n  mode: observe\n  api_key: example-test-key\n", encoding="utf-8")
            await init_app_settings(str(path))
            service = JevDecisionService()
            self.assertEqual(service.config.mode, "observe")
            self.assertEqual(service.config.api_key, "example-test-key")
            self.assertTrue(service.active)

    async def test_environment_master_mode_controls_both_integrations(self):
        settings = {
            "mode": "enforce", "api_key": "test-key",
            "min_tools_for_selection": 2, "max_selected_tools": 1,
        }
        candidates = tools(2)
        for mode, expected_gate, expected_selection, expected_calls in [
            ("disabled", True, None, 0),
            ("observe", True, None, 2),
            ("enforce", False, candidates[:1], 2),
        ]:
            with self.subTest(mode=mode):
                requests = []

                def respond(request):
                    body = json.loads(request.content)
                    requests.append(body)
                    values = (
                        {"needs_tools": 0.01} if "needs_tools" in body["questions"]
                        else {"relevant_0": 0.99, "relevant_1": 0.01}
                    )
                    return httpx.Response(200, json={
                        "model": "jev-1.13.0",
                        "answers": {name: {"type": "noul", "noul": value} for name, value in values.items()},
                        "usage": {"input_tokens": 10, "output_tokens": 1},
                    })

                with patch.object(app_settings, "jev", settings), patch.dict(os.environ, {"JEV_MODE": mode}):
                    service = JevDecisionService(transport=httpx.MockTransport(respond))
                self.assertEqual(await service.should_run_tools([], candidates), expected_gate)
                self.assertEqual(await service.select_tools([], candidates), expected_selection)
                self.assertEqual(len(requests), expected_calls)

    async def test_unset_or_empty_environment_preserves_yaml_and_default_mode(self):
        for environment in ({}, {"JEV_MODE": ""}, {"JEV_MODE": "   "}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                with patch.object(app_settings, "jev", {"mode": "observe"}):
                    self.assertEqual(JevDecisionService().config.mode, "observe")
                with patch.object(app_settings, "jev", {}):
                    self.assertEqual(JevDecisionService().config.mode, "disabled")

    async def test_environment_mode_preserves_individual_switches_and_missing_key_fallback(self):
        for settings in [
            {"api_key": "test-key", "tool_gate_enabled": False, "tool_selector_enabled": False},
            {},
        ]:
            with self.subTest(settings=settings):
                with patch.object(app_settings, "jev", settings), patch.dict(os.environ, {"JEV_MODE": "enforce"}):
                    service = JevDecisionService()
                service._evaluate = AsyncMock()
                self.assertTrue(await service.should_run_tools([], tools(10)))
                self.assertIsNone(await service.select_tools([], tools(10)))
                service._evaluate.assert_not_awaited()

    async def test_explicit_configuration_is_not_overridden_by_process_environment(self):
        with patch.dict(os.environ, {"JEV_MODE": "enforce"}):
            config = JevConfig(mode="disabled")
            self.assertIs(JevDecisionService(config).config, config)

    async def test_invalid_environment_mode_disables_both_integrations_without_blocking_chat(self):
        with (
            patch.object(app_settings, "jev", {"mode": "enforce", "api_key": "test-key"}),
            patch.dict(os.environ, {"JEV_MODE": "enabled"}),
        ):
            service = JevDecisionService()
        service._evaluate = AsyncMock()
        self.assertEqual(service.config.mode, "disabled")
        self.assertTrue(await service.should_run_tools([], tools(10)))
        self.assertIsNone(await service.select_tools([], tools(10)))
        service._evaluate.assert_not_awaited()

    async def test_logs_omit_credentials_messages_and_provider_error_body(self):
        logs = []
        sink = logger.add(lambda message: logs.append(str(message)))
        try:
            service = self.service()
            service._transport = httpx.MockTransport(lambda request: httpx.Response(
                401, json={"error": "secret-provider-body"},
            ))
            self.assertTrue(await service.should_run_tools(
                [{"role": "user", "content": "private-chat-marker"}], tools(1),
            ))
        finally:
            logger.remove(sink)
        captured = "\n".join(logs)
        self.assertIn("http_401", captured)
        for secret in ["test-secret", "private-chat-marker", "secret-provider-body"]:
            self.assertNotIn(secret, captured)


if __name__ == "__main__":
    unittest.main()
