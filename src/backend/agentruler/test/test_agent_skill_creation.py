import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from agentruler.settings import init_app_settings


class AgentSkillCreationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_app_settings()
        from fastapi import FastAPI
        from agentruler.api.v1.agent_skill import get_login_user, router

        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1")
        self.app.dependency_overrides[get_login_user] = lambda: SimpleNamespace(user_id="skill-test-user")

    async def test_create_skill_with_deepseek_structured_tool_calling(self):
        from agentruler.api.services.usage_stats import UsageStatsService
        from agentruler.core.models.manager import ModelManager
        from agentruler.database.dao.agent_skill import AgentSkillDao

        payload = {"name": "会议纪要整理", "description": "根据会议记录提取关键决策、待办事项、负责人和截止时间。"}
        provider_requests = []

        def provider(request):
            body = json.loads(request.content)
            provider_requests.append(body)
            # Reproduce the provider error that previously prevented Skill creation.
            if body.get("thinking", {}).get("type") != "disabled":
                return httpx.Response(400, json={"error": {
                    "message": "Thinking mode does not support this tool_choice",
                    "type": "invalid_request_error",
                }})
            return httpx.Response(200, json={
                "id": "chatcmpl-skill-test",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_skill_name",
                        "type": "function",
                        "function": {
                            "name": "AgentSkillResponseFormat",
                            "arguments": json.dumps({"as_tool_name": "meeting_minutes_skill"}),
                        },
                    }]},
                    "finish_reason": "tool_calls",
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            })

        settings = SimpleNamespace(multi_models=SimpleNamespace(conversation_model=SimpleNamespace(
            model_name="deepseek-flash", api_key="test-key", base_url="https://api.deepseek.com",
        )))
        original_model = ModelManager.get_conversation_model
        with httpx.Client(transport=httpx.MockTransport(provider)) as provider_client:
            def model(**kwargs):
                return original_model(http_client=provider_client, max_retries=0, **kwargs)

            with (
                patch("agentruler.core.models.manager.app_settings", settings),
                patch.object(ModelManager, "get_conversation_model", side_effect=model),
                patch.object(AgentSkillDao, "create_agent_skill", new_callable=AsyncMock) as save,
                patch.object(UsageStatsService, "sync_create_usage_stats"),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=self.app), base_url="http://test",
                ) as client:
                    response = await client.post("/api/v1/agent_skill/create", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["status_code"], 200, result)
        self.assertEqual(result["data"]["as_tool_name"], "meeting_minutes_skill")
        self.assertEqual(len(provider_requests), 1)
        save.assert_awaited_once()
        saved = save.await_args.args[0]
        self.assertEqual(saved.user_id, "skill-test-user")
        self.assertEqual(saved.name, payload["name"])
        self.assertEqual(saved.description, payload["description"])
        files = saved.folder["folder"]
        self.assertEqual([item["name"] for item in files], ["SKILL.md", "reference", "scripts"])
        self.assertIn(payload["description"], files[0]["content"])

    async def test_creation_failure_returns_http_error(self):
        from agentruler.api.services.agent_skill import AgentSkillService

        with patch.object(
            AgentSkillService, "create_agent_skill", new_callable=AsyncMock,
            side_effect=RuntimeError("skill creation failed"),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), base_url="http://test",
            ) as client:
                response = await client.post("/api/v1/agent_skill/create", json={
                    "name": "会议纪要整理", "description": "将会议记录整理为纪要。",
                })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "skill creation failed")


if __name__ == "__main__":
    unittest.main()
