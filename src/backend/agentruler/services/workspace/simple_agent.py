import copy
import asyncio
import re
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID
from loguru import logger
from typing import List, Dict, Any
from pydantic import BaseModel
from langgraph.types import Command
from langgraph.prebuilt.tool_node import ToolCallRequest
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, AIMessageChunk

from agentruler.core.callbacks import usage_metadata_callback
from agentruler.tools import WorkSpacePlugins
from agentruler.schemas.usage_stats import UsageStatsAgentType
from agentruler.schemas.workspace import WorkSpaceAgents
from agentruler.api.services.tool import ToolService
from agentruler.services.mcp.manager import MCPManager
from agentruler.prompts.completion import GenerateTitlePrompt
from agentruler.utils.convert import convert_mcp_config
from agentruler.core.models.manager import ModelManager
from agentruler.api.services.mcp_user_config import MCPUserConfigService
from agentruler.api.services.usage_stats import UsageStatsService
from agentruler.api.services.workspace_session import WorkSpaceSessionService
from agentruler.database.models.workspace_session import WorkSpaceSessionCreate, WorkSpaceSessionContext


_SENSITIVE_ARGUMENT_KEY = re.compile(r"token|api[_-]?key|secret|password|authorization|cookie|credential", re.I)


def _redact_mcp_arguments(arguments: dict) -> dict:
    """Only store/display safe tool arguments in stream events and chat history."""
    def redact(value):
        if isinstance(value, dict):
            return {
                key: "***" if _SENSITIVE_ARGUMENT_KEY.search(str(key)) else redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return redact(arguments)


class MCPConfig(BaseModel):
    url: str
    type: str = "sse"
    tools: List[str] = []
    server_name: str
    mcp_server_id: str


class WorkSpaceSimpleAgent:
    """

    Sub-agent that can invoke **both user-provided plugin functions and MCP tools**.  It analyses the
    current conversation, decides which tool(s) should be run, performs the calls asynchronously and
    pushes progress/result events back to the main :class:`mars_agent.agent.MarsAgent`.

    Responsibilities
    ---------------
    1. Select appropriate plugin or MCP tool according to conversation context.
    2. Execute the tool in an asynchronous, non-blocking way.
    3. Report every progress, success or error through the shared ``EventManager``.
    4. **Does not generate any LLM response** – that task belongs to the main agent.

    Usage
    -----
    ``SimpleAgent`` instances are automatically created by.
    End-users rarely need to touch this class directly.
    """

    def __init__(self,
                 model_config,
                 user_id: str,
                 session_id: str,
                 plugins: List[str] = [],
                 mcp_configs: List[MCPConfig] = []):

        # Simple-agent only needs tool calling model, not conversation model
        self.model = ModelManager.get_user_model(preserve_reasoning=True, **model_config)
        self.plugin_tools = []
        self.mcp_tools = []
        self.mcp_configs = mcp_configs
        self.tools = []
        self.mcp_manager = MCPManager(convert_mcp_config([mcp_config.model_dump() for mcp_config in mcp_configs]))
        self.plugins = plugins
        self.session_id = session_id

        self.user_id = user_id

        # Find user config by server name
        self.server_dict: dict[str, Any] = {}
        self.tool_descriptions: dict[str, dict[str, str]] = {}

        # Initialize state management
        self._initialized = False
        self._tool_event_queue: asyncio.Queue | None = None


    async def init_simple_agent(self):
        """Initialize sub-agent - with resource management"""
        try:
            if self._initialized:
                logger.info("Simple Agent already initialized")
                return
            await self.setup_mcp_tools()
            await self.setup_plugin_tools()

            self.middlewares = await self.setup_middlewares()

            self.tools = self.plugin_tools + self.mcp_tools
            self._initialized = True
            self.react_agent = self.setup_react_agent()

            logger.info("Simple Agent initialized successfully")
        except Exception as err:
            logger.error(f"Failed to initialize Simple Agent: {err}")
            raise

    def setup_react_agent(self):
        return create_agent(
            model=self.model,
            tools=self.tools,
            middleware=self.middlewares
        )

    async def _get_visible_mcp_arguments(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        """Include fixed query parameters used by MCPs generated from HTTP APIs."""
        visible_arguments = copy.deepcopy(arguments)
        server_config = next((config for config in self.mcp_configs if config.server_name == server_name), None)
        if server_config is not None:
            try:
                path_parts = urlsplit(server_config.url).path.rstrip("/").split("/")
                server_key = path_parts[-2] if path_parts[-1] == "sse" else path_parts[-1]
                register_mcp_id = str(UUID(server_key))
                from agentruler.database.dao.register_mcp import RegisterMcpDao
                tool = await RegisterMcpDao.get_tool_by_name(register_mcp_id, tool_name)
                if tool and tool.api_info:
                    api_url = tool.api_info.get("base_url", "") + tool.api_info.get("path", "")
                    for key, value in parse_qsl(urlsplit(api_url).query, keep_blank_values=True):
                        visible_arguments.setdefault(key, value)
            except (ValueError, KeyError, TypeError):
                pass  # External MCP URLs and tools have no local API metadata.
            except Exception as err:
                logger.warning(f"Could not load fixed MCP arguments for {tool_name}: {err}")
        return _redact_mcp_arguments(visible_arguments)

    async def setup_middlewares(self):
        @wrap_tool_call
        async def handler_call_mcp_tool(
            request: ToolCallRequest,
            handler
        ) -> ToolMessage | Command:
            if self.is_mcp_tool(request.tool_call["name"]):
                tool_name = request.tool_call["name"]
                server_name = next(
                    (name for name, tools in self.server_dict.items() if tool_name in tools),
                    "MCP"
                )
                event_data = {
                    "id": request.tool_call["id"],
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "description": self.tool_descriptions.get(server_name, {}).get(tool_name, ""),
                    "arguments": await self._get_visible_mcp_arguments(
                        server_name, tool_name, request.tool_call["args"]
                    ),
                    "status": "START"
                }
                if self._tool_event_queue is not None:
                    self._tool_event_queue.put_nowait({"event": "mcp_tool", "data": event_data.copy()})

                try:
                    # 针对鉴权的MCP Server需要用户的单独配置，例如飞书、邮箱
                    mcp_config = await MCPUserConfigService.get_mcp_user_config(
                        self.user_id, self.get_mcp_id_by_tool(tool_name)
                    )
                    request.tool_call["args"].update(mcp_config)
                    tool_result = await handler(request)
                except Exception:
                    if self._tool_event_queue is not None:
                        self._tool_event_queue.put_nowait({
                            "event": "mcp_tool", "data": {**event_data, "status": "ERROR"}
                        })
                    raise

                if self._tool_event_queue is not None:
                    status = "ERROR" if getattr(tool_result, "status", None) == "error" else "END"
                    self._tool_event_queue.put_nowait({
                        "event": "mcp_tool", "data": {**event_data, "status": status}
                    })
            else:
                tool_result = await handler(request)

            return tool_result

        return [handler_call_mcp_tool]

    async def setup_mcp_tools(self):
        """Initialize MCP tools - with error handling"""
        if not self.mcp_configs:
            self.mcp_tools = []
            return

        try:
            # Establish connection with MCP Server
            self.mcp_tools = await self.mcp_manager.get_mcp_tools()

            mcp_servers_info = await self.mcp_manager.show_mcp_tools()
            self.server_dict = {server_name: [tool["name"] for tool in tools_info] for server_name, tools_info in
                                mcp_servers_info.items()}
            self.tool_descriptions = {
                server_name: {tool["name"]: tool.get("description") or "" for tool in tools_info}
                for server_name, tools_info in mcp_servers_info.items()
            }

            logger.info(f"Loaded {len(self.mcp_tools)} MCP tools from MCP servers")

        except Exception as err:
            logger.error(f"Failed to initialize MCP tools: {err}")
            self.mcp_tools = []

    async def setup_plugin_tools(self):
        """Initialize plugin tools - with error handling"""
        try:
            tools_name = await ToolService.get_tool_name_by_id(self.plugins)
            for name in tools_name:
                self.plugin_tools.append(WorkSpacePlugins[name])

            logger.info(f"Loaded {len(self.plugin_tools)} plugin tools")

        except Exception as err:
            logger.error(f"Failed to initialize plugin tools: {err}")
            self.plugin_tools = []

    async def ainvoke(self, messages: List[BaseMessage]):
        """Sub-agent tool execution - only return tool execution results, no model reply"""
        if not self._initialized:
            await self.init_simple_agent()

        try:
            react_agent_task = None
            if self.tools and len(self.tools) != 0:
                react_agent_task = asyncio.create_task(self.react_agent.ainvoke({"messages": messages}))

            # Wait for tool execution to complete
            if react_agent_task:
                results = await react_agent_task
                messages = results["messages"][:-1]  # Remove messages that didn't hit tools

                messages = [msg for msg in messages if
                            isinstance(msg, ToolMessage) or (isinstance(msg, AIMessage) and msg.tool_calls)]

                return messages
            else:
                return []

        except Exception as err:
            return []

    async def _generate_title(self, query):
        session = await WorkSpaceSessionService.get_workspace_session_from_id(self.session_id, self.user_id)
        if session:
            return session.get("title")
        title_prompt = GenerateTitlePrompt.format(query=query)
        response = await self.model.ainvoke(title_prompt, config={"callbacks": [usage_metadata_callback]})
        return response.content

    async def _add_workspace_session(self, title, contexts: WorkSpaceSessionContext):
        session = await WorkSpaceSessionService.get_workspace_session_from_id(self.session_id, self.user_id)
        if session:
            await WorkSpaceSessionService.update_workspace_session_contexts(
                session_id=self.session_id,
                session_context=contexts.model_dump()
            )
        else:
            await WorkSpaceSessionService.create_workspace_session(
                WorkSpaceSessionCreate(
                    title=title,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    contexts=[contexts.model_dump()],
                    agent=WorkSpaceAgents.SimpleAgent.value))

    async def astream(self, messages: List[BaseMessage]):
        if not self._initialized:
            await self.init_simple_agent()
        user_messages = copy.deepcopy(messages)

        generate_title_task = asyncio.create_task(self._generate_title(user_messages[-1].content))
        mcp_tool_calls = []
        reasoning_text = ""
        try:
            react_agent_task = None
            if self.tools and len(self.tools) != 0:
                tool_event_queue = asyncio.Queue()
                self._tool_event_queue = tool_event_queue

                async def run_tool_agent():
                    try:
                        result = None
                        async for mode, data in self.react_agent.astream(
                            input={"messages": messages},
                            config={"callbacks": [usage_metadata_callback]},
                            stream_mode=["messages", "values"]
                        ):
                            if mode == "messages":
                                message_chunk, _ = data
                                reasoning = message_chunk.additional_kwargs.get("reasoning_content")
                                if isinstance(reasoning, str) and reasoning:
                                    tool_event_queue.put_nowait({
                                        "event": "reasoning_chunk", "data": {"chunk": reasoning}
                                    })
                            elif mode == "values":
                                result = data
                        return result
                    finally:
                        tool_event_queue.put_nowait(None)

                react_agent_task = asyncio.create_task(run_tool_agent())

            # Wait for tool execution to complete
            if react_agent_task:
                while (event := await tool_event_queue.get()) is not None:
                    if event["event"] == "reasoning_chunk":
                        reasoning_text += event["data"]["chunk"]
                    else:
                        event_data = event["data"]
                        if event_data["status"] == "START":
                            mcp_tool_calls.append(event_data.copy())
                        else:
                            for tool_call in reversed(mcp_tool_calls):
                                if tool_call["id"] == event_data["id"]:
                                    tool_call["status"] = event_data["status"]
                                    break
                    yield event

                results = await react_agent_task
                messages = results["messages"][:-1]  # Remove messages that didn't hit tools

                messages = [msg for msg in messages if
                            isinstance(msg, ToolMessage) or (isinstance(msg, AIMessage) and msg.tool_calls)]
        except Exception as err:
            raise ValueError from err
        finally:
            if react_agent_task is not None and not react_agent_task.done():
                react_agent_task.cancel()
            self._tool_event_queue = None
        messages = user_messages + messages

        final_answer = ""
        async for chunk in self.model.astream(input=messages, config={"callbacks": [usage_metadata_callback]}):
            reasoning = chunk.additional_kwargs.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                reasoning_text += reasoning
                yield {
                    "event": "reasoning_chunk",
                    "data": {"chunk": reasoning}
                }

            if isinstance(chunk.content, str) and chunk.content:
                yield {
                    "event": "task_result",
                    "data": {"message": chunk.content}
                }
                final_answer += chunk.content

        await generate_title_task
        title = generate_title_task.result() if generate_title_task.done() else None

        await self._add_workspace_session(
            title=title,
            contexts=WorkSpaceSessionContext(
                query=user_messages[-1].content,
                mcp_tool_calls=mcp_tool_calls,
                reasoning=reasoning_text,
                answer=final_answer
            ))


    async def _record_agent_token_usage(self, response: AIMessage | AIMessageChunk | BaseMessage, model):
        if response.usage_metadata:
            await UsageStatsService.create_usage_stats(
                model=model,
                user_id=self.user_id,
                agent=UsageStatsAgentType.simple_agent,
                input_tokens=response.usage_metadata.get("input_tokens"),
                output_tokens=response.usage_metadata.get("output_tokens")
            )

    def is_mcp_tool(self, tool_name: str):
        """Determine if it's an MCP tool and return the corresponding tool instance"""
        mcp_names = [tool.name for tool in self.mcp_tools]
        plugin_names = [tool.name for tool in self.plugin_tools]

        if tool_name in mcp_names:
            return True
        elif tool_name in plugin_names:
            return False
        else:
            raise ValueError(f"Tool '{tool_name}' not found in either MCP or plugin tools.")

    def get_mcp_id_by_tool(self, tool_name):
        for server_name, tools in self.server_dict.items():
            if tool_name in tools:
                for config in self.mcp_configs:
                    if server_name == config.server_name:
                        return config.mcp_server_id
        return None
