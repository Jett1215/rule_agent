"""Exercise the real workspace flow while isolating database and provider imports."""

import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage

from agentruler.schemas.common import JevConfig, MultiModels
from agentruler.services.decision.jev import JevDecisionService
from agentruler.settings import app_settings


def _boundary_module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


def _load_workspace_module():
    """Import production methods without initializing SQL engines or optional plugins."""
    name = "agentruler.services.workspace.simple_agent"
    package = importlib.import_module("agentruler.services.workspace")
    missing = object()
    old_attribute = getattr(package, "simple_agent", missing)
    boundaries = {
        "agentruler.core.callbacks": {"usage_metadata_callback": None},
        "agentruler.tools": {"WorkSpacePlugins": {}},
        "agentruler.api.services.tool": {"ToolService": object},
        "agentruler.services.mcp.manager": {"MCPManager": object},
        "agentruler.utils.convert": {"convert_mcp_config": lambda value: value},
        "agentruler.core.models.manager": {"ModelManager": object},
        "agentruler.api.services.mcp_user_config": {"MCPUserConfigService": object},
        "agentruler.api.services.usage_stats": {"UsageStatsService": object},
        "agentruler.api.services.workspace_session": {"WorkSpaceSessionService": object},
        "agentruler.database.models.workspace_session": {
            "WorkSpaceSessionCreate": SimpleNamespace,
            "WorkSpaceSessionContext": SimpleNamespace,
        },
    }
    stubs = {module: _boundary_module(module, **attributes) for module, attributes in boundaries.items()}
    try:
        with patch.dict(sys.modules, stubs), patch.object(app_settings, "multi_models", MultiModels()):
            # Force a separate import even when another test has loaded this module.
            sys.modules.pop(name, None)
            return importlib.import_module(name)
    finally:
        if old_attribute is missing:
            if hasattr(package, "simple_agent"):
                delattr(package, "simple_agent")
        else:
            package.simple_agent = old_attribute


class WorkspaceJevGateTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = _load_workspace_module()

    def setUp(self):
        self.messages = [
            SystemMessage(content="Previous request: check today's weather in Hangzhou."),
            HumanMessage(content="Check tomorrow too."),
        ]
        self.tool_call = AIMessage(content="", tool_calls=[{
            "name": "weather", "args": {}, "id": "weather-call",
        }])
        self.tool_result = ToolMessage(content="Sunny", tool_call_id="weather-call", name="weather")

    def _make_agent(self, *, mode="enforce", probability=0.99, failed=False, with_tools=True):
        agent = self.workspace.WorkSpaceSimpleAgent.__new__(self.workspace.WorkSpaceSimpleAgent)
        agent._initialized = True
        agent._tool_event_queue = None
        agent.tools = [SimpleNamespace(name="weather", description="Read the latest weather")] if with_tools else []
        service = JevDecisionService(JevConfig(mode=mode, api_key="unit-test-placeholder"))
        service._evaluate = AsyncMock(return_value=None if failed else {"needs_tools": probability})
        service.should_run_tools = AsyncMock(wraps=service.should_run_tools)
        agent.jev_decisions = service
        agent._generate_title = AsyncMock(return_value="Weather")
        agent._add_workspace_session = AsyncMock()

        async def model_stream(**kwargs):
            yield AIMessageChunk(content="", additional_kwargs={"reasoning_content": "final reasoning"})
            yield AIMessageChunk(content="Final answer")

        async def tool_agent_stream(**kwargs):
            queue = agent._tool_event_queue
            queue.put_nowait({"event": "mcp_tool", "data": {
                "id": "weather-call", "tool_name": "weather", "status": "START",
            }})
            yield "messages", (AIMessageChunk(
                content="", additional_kwargs={"reasoning_content": "tool reasoning"},
            ), {})
            queue.put_nowait({"event": "mcp_tool", "data": {
                "id": "weather-call", "tool_name": "weather", "status": "END",
            }})
            yield "values", {"messages": [
                *kwargs["input"]["messages"], self.tool_call, self.tool_result,
                AIMessage(content="Discard the tool agent's final text"),
            ]}

        agent.model = SimpleNamespace(astream=Mock(side_effect=model_stream))
        agent.react_agent = SimpleNamespace(
            astream=Mock(side_effect=tool_agent_stream),
            ainvoke=AsyncMock(return_value={"messages": [
                *self.messages, self.tool_call, self.tool_result, AIMessage(content="Discard this"),
            ]}),
        )
        return agent

    async def _collect_stream(self, agent):
        return [event async for event in agent.astream(self.messages)]

    async def test_needed_tools_keep_agent_events_and_final_answer(self):
        agent = self._make_agent()

        events = await self._collect_stream(agent)

        agent.jev_decisions.should_run_tools.assert_awaited_once_with(self.messages, agent.tools)
        agent.react_agent.astream.assert_called_once()
        self.assertEqual(agent.react_agent.astream.call_args.kwargs["input"], {"messages": self.messages})
        agent.model.astream.assert_called_once()
        self.assertEqual(agent.model.astream.call_args.kwargs["input"], [
            *self.messages, self.tool_call, self.tool_result,
        ])
        self.assertEqual([event["data"]["status"] for event in events if event["event"] == "mcp_tool"], ["START", "END"])
        self.assertIn({"event": "task_result", "data": {"message": "Final answer"}}, events)
        saved = agent._add_workspace_session.await_args.kwargs
        self.assertEqual(saved["title"], "Weather")
        self.assertEqual(saved["contexts"].answer, "Final answer")
        self.assertEqual(saved["contexts"].reasoning, "tool reasoningfinal reasoning")
        self.assertEqual(saved["contexts"].mcp_tool_calls[0]["status"], "END")
        self.assertIsNone(agent._tool_event_queue)

    async def test_enforce_skip_keeps_original_context_exactly_once(self):
        agent = self._make_agent(probability=0.01)

        events = await self._collect_stream(agent)

        agent.react_agent.astream.assert_not_called()
        agent.jev_decisions.should_run_tools.assert_awaited_once_with(self.messages, agent.tools)
        self.assertEqual(agent.model.astream.call_args.kwargs["input"], self.messages)
        self.assertEqual(len(agent.model.astream.call_args.kwargs["input"]), 2)
        self.assertEqual(len(self.messages), 2)
        agent._generate_title.assert_awaited_once_with("Check tomorrow too.")
        agent._add_workspace_session.assert_awaited_once()
        self.assertEqual(agent._add_workspace_session.await_args.kwargs["contexts"].mcp_tool_calls, [])
        self.assertEqual(events[-1], {"event": "task_result", "data": {"message": "Final answer"}})

    async def test_observe_and_failed_decision_still_run_tool_agent(self):
        for options in ({"mode": "observe", "probability": 0.01}, {"failed": True}):
            with self.subTest(options=options):
                agent = self._make_agent(**options)

                await self._collect_stream(agent)

                agent.react_agent.astream.assert_called_once()
                agent.model.astream.assert_called_once()
                agent.jev_decisions.should_run_tools.assert_awaited_once_with(self.messages, agent.tools)

    async def test_no_tools_bypasses_gate_and_uses_context_once(self):
        agent = self._make_agent(with_tools=False)

        await self._collect_stream(agent)

        agent.jev_decisions.should_run_tools.assert_not_awaited()
        agent.jev_decisions._evaluate.assert_not_awaited()
        agent.react_agent.astream.assert_not_called()
        self.assertEqual(agent.model.astream.call_args.kwargs["input"], self.messages)

    async def test_ainvoke_applies_the_same_gate_without_generating_a_final_answer(self):
        cases = [
            ({"probability": 0.99}, True),
            ({"probability": 0.01}, False),
            ({"mode": "observe", "probability": 0.01}, True),
            ({"failed": True}, True),
            ({"with_tools": False}, False),
        ]
        for options, should_run in cases:
            with self.subTest(options=options):
                agent = self._make_agent(**options)

                result = await agent.ainvoke(self.messages)

                if should_run:
                    agent.react_agent.ainvoke.assert_awaited_once_with({"messages": self.messages})
                    self.assertEqual(result, [self.tool_call, self.tool_result])
                else:
                    agent.react_agent.ainvoke.assert_not_awaited()
                    self.assertEqual(result, [])
                if agent.tools:
                    agent.jev_decisions.should_run_tools.assert_awaited_once_with(self.messages, agent.tools)
                else:
                    agent.jev_decisions.should_run_tools.assert_not_awaited()
                agent.model.astream.assert_not_called()
                agent._generate_title.assert_not_awaited()
                agent._add_workspace_session.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
