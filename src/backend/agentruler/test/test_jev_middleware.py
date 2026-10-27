import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import Field

from agentruler.core.agents.jev_middleware import JevToolSelectorMiddleware


@tool
def first_tool() -> str:
    """Read the first source."""
    return "first result"


@tool
def second_tool() -> str:
    """Read the second source."""
    return "second result"


class RecordingToolModel(BaseChatModel):
    """Run the actual LangChain agent graph with deterministic model responses."""

    responses: list[AIMessage]
    bindings: list[list[str]] = Field(default_factory=list)
    response_index: int = 0

    @property
    def _llm_type(self):
        return "recording-tool-model"

    def bind_tools(self, tools, **kwargs):
        self.bindings.append([item.name for item in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        response = self.responses[self.response_index]
        self.response_index += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, **kwargs)


class JevToolSelectorMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_agent_reselects_after_each_tool_result_and_falls_back(self):
        tools = [first_tool, second_tool]
        service = SimpleNamespace(select_tools=AsyncMock(side_effect=[
            [first_tool], [second_tool], None,
        ]))
        model = RecordingToolModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "first_tool", "args": {}, "id": "first-call",
            }]),
            AIMessage(content="", tool_calls=[{
                "name": "second_tool", "args": {}, "id": "second-call",
            }]),
            AIMessage(content="done"),
        ])
        agent = create_agent(
            model=model,
            tools=tools,
            middleware=[JevToolSelectorMiddleware(service)],
        )

        result = await agent.ainvoke({"messages": [HumanMessage(content="Read both sources")]})

        self.assertEqual(model.bindings, [
            ["first_tool"], ["second_tool"], ["first_tool", "second_tool"],
        ])
        calls = service.select_tools.await_args_list
        self.assertEqual(len(calls), 3)
        for call in calls:
            self.assertEqual([item.name for item in call.args[1]], ["first_tool", "second_tool"])
        self.assertIsInstance(calls[1].args[0][-1], ToolMessage)
        self.assertEqual(calls[1].args[0][-1].content, "first result")
        self.assertEqual(calls[2].args[0][-1].content, "second result")
        self.assertEqual(result["messages"][-1].content, "done")
        self.assertEqual([item.name for item in tools], ["first_tool", "second_tool"])

    async def test_filtered_context_keeps_static_tool_execution_registry(self):
        service = SimpleNamespace(select_tools=AsyncMock(side_effect=[[first_tool], None]))
        model = RecordingToolModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "second_tool", "args": {}, "id": "second-call",
            }]),
            AIMessage(content="done"),
        ])
        agent = create_agent(
            model=model,
            tools=[first_tool, second_tool],
            middleware=[JevToolSelectorMiddleware(service)],
        )

        result = await agent.ainvoke({"messages": [HumanMessage(content="Read a source")]})

        tool_results = [message for message in result["messages"] if isinstance(message, ToolMessage)]
        self.assertEqual(model.bindings[0], ["first_tool"])
        self.assertEqual(tool_results[0].content, "second result")

    async def test_service_failure_passes_original_request_to_model(self):
        service = SimpleNamespace(select_tools=AsyncMock(side_effect=TimeoutError()))
        middleware = JevToolSelectorMiddleware(service)
        request = ModelRequest(
            model=RecordingToolModel(responses=[]),
            messages=[HumanMessage(content="Read a source")],
            tools=[first_tool, second_tool],
        )
        response = ModelResponse(result=[AIMessage(content="done")])
        handler = AsyncMock(return_value=response)

        self.assertIs(await middleware.awrap_model_call(request, handler), response)
        handler.assert_awaited_once_with(request)
        self.assertEqual(request.tools, [first_tool, second_tool])

    async def test_explicit_empty_selection_is_applied_without_mutating_request(self):
        service = SimpleNamespace(select_tools=AsyncMock(return_value=[]))
        middleware = JevToolSelectorMiddleware(service)
        request = ModelRequest(
            model=RecordingToolModel(responses=[]),
            messages=[HumanMessage(content="Hello")],
            tools=[first_tool, second_tool],
        )
        handler = AsyncMock(return_value=ModelResponse(result=[AIMessage(content="Hello")]))

        await middleware.awrap_model_call(request, handler)

        filtered_request = handler.await_args.args[0]
        self.assertIsNot(filtered_request, request)
        self.assertEqual(filtered_request.tools, [])
        self.assertEqual(request.tools, [first_tool, second_tool])

    async def test_unknown_provider_tool_is_preserved_without_selection(self):
        service = SimpleNamespace(select_tools=AsyncMock())
        request = ModelRequest(
            model=RecordingToolModel(responses=[]),
            messages=[HumanMessage(content="Search")],
            tools=[first_tool, {"type": "web_search"}],
        )
        handler = AsyncMock(return_value=ModelResponse(result=[AIMessage(content="done")]))

        await JevToolSelectorMiddleware(service).awrap_model_call(request, handler)

        service.select_tools.assert_not_awaited()
        handler.assert_awaited_once_with(request)

    async def test_invalid_candidates_cannot_expand_or_replace_authorized_tools(self):
        for selected in ([second_tool], [first_tool, first_tool], [first_tool.model_copy()]):
            with self.subTest(selected=selected):
                service = SimpleNamespace(select_tools=AsyncMock(return_value=selected))
                request = ModelRequest(
                    model=RecordingToolModel(responses=[]),
                    messages=[HumanMessage(content="Read a source")],
                    tools=[first_tool],
                )
                handler = AsyncMock(return_value=ModelResponse(result=[AIMessage(content="done")]))

                await JevToolSelectorMiddleware(service).awrap_model_call(request, handler)

                handler.assert_awaited_once_with(request)
                self.assertEqual(request.tools, [first_tool])


if __name__ == "__main__":
    unittest.main()
