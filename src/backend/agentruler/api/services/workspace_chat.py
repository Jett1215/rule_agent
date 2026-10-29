"""Compose daily conversations without changing the selected Agent's definition."""

import copy
from contextlib import aclosing

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agentruler.api.services.agent import AgentService
from agentruler.api.services.knowledge import KnowledgeService
from agentruler.api.services.llm import LLMService
from agentruler.api.services.mcp_server import MCPService
from agentruler.api.services.tool import ToolService
from agentruler.api.services.workspace_session import WorkSpaceSessionService
from agentruler.core.agents.general_agent import AgentConfig, GeneralAgent
from agentruler.database.dao.agent_skill import AgentSkillDao
from agentruler.database.models.user import SystemUser
from agentruler.database.models.workspace_session import WorkSpaceSessionContext, WorkSpaceSessionCreate
from agentruler.prompts.completion import SYSTEM_PROMPT
from agentruler.schemas.workspace import WorkSpaceSimpleTask
from agentruler.services.workspace.simple_agent import MCPConfig, WorkSpaceSimpleAgent
from agentruler.utils.contexts import set_agent_name_context
from agentruler.utils.helpers import build_completion_system_prompt


class WorkspaceChatService:
    @classmethod
    async def prepare(cls, task: WorkSpaceSimpleTask, user_id: str):
        """Resolve defaults and permissions before opening the SSE response."""
        if not task.query.strip():
            raise HTTPException(status_code=422, detail="请输入消息内容")
        session = await WorkSpaceSessionService.get_workspace_session_from_id(task.session_id, user_id)
        if session and session.get("agent") != "simple":
            raise HTTPException(status_code=409, detail="该会话属于灵寻模式，请从对应模式继续")
        contexts = session.get("contexts", []) if session else []
        previous = next((item["config"] for item in reversed(contexts) if isinstance(item.get("config"), dict)), {})
        agent_id = task.agent_id if "agent_id" in task.model_fields_set else previous.get("agent_id")
        agent_id = agent_id or None
        agent = None
        if agent_id:
            agent = await AgentService.select_agent_by_id(agent_id)
            if not agent or agent.get("user_id") not in (user_id, SystemUser):
                raise HTTPException(status_code=403, detail="智能体不可用或无权访问")

        defaults = {
            "agent_id": agent_id,
            "model_id": agent.get("llm_id") if agent else None,
            "plugins": list(agent.get("tool_ids") or []) if agent else [],
            "mcp_servers": list(agent.get("mcp_ids") or []) if agent else [],
        }
        if previous.get("agent_id") == agent_id:
            defaults.update(previous)
        config = {**defaults, "agent_id": agent_id}
        for key in ("model_id", "plugins", "mcp_servers"):
            value = getattr(task, key)
            if value is not None:
                config[key] = value
        if not config.get("model_id"):
            raise HTTPException(status_code=422, detail="请选择可用模型")
        model, servers = await cls._validate_resources(config, agent, user_id)
        return session, config, agent, model, servers

    @classmethod
    async def validate_agent_resources(cls, agent: dict | None, user_id: str):
        """Apply the same execution permissions to existing Agent dialogs."""
        if not agent or agent.get("user_id") not in (user_id, SystemUser):
            raise HTTPException(status_code=403, detail="智能体不可用或无权访问")
        await cls._validate_resources({
            "model_id": agent.get("llm_id"),
            "plugins": agent.get("tool_ids") or [],
            "mcp_servers": agent.get("mcp_ids") or [],
        }, agent, user_id)

    @classmethod
    async def _validate_resources(cls, config: dict, agent: dict | None, user_id: str):
        model = None
        # Legacy Agents may intentionally use the configured system default model.
        if config.get("model_id"):
            model = await LLMService.get_llm_by_id(config["model_id"])
            if not model or model.get("user_id") not in (user_id, SystemUser):
                raise HTTPException(status_code=403, detail="模型不可用或无权访问")
            if str(model.get("llm_type", "LLM")).upper() != "LLM":
                raise HTTPException(status_code=422, detail="请选择对话模型")

        visible_tools = await ToolService.get_visible_tool_by_user(user_id)
        if not set(config["plugins"]).issubset({item["tool_id"] for item in visible_tools}):
            raise HTTPException(status_code=403, detail="工具不可用或无权访问")
        visible_mcp = await MCPService.get_all_servers(user_id)
        by_mcp_id = {item["mcp_server_id"]: item for item in visible_mcp}
        if not set(config["mcp_servers"]).issubset(by_mcp_id):
            raise HTTPException(status_code=403, detail="MCP 服务不可用或无权访问")
        if agent:
            for knowledge_id in agent.get("knowledge_ids") or []:
                try:
                    owner = await KnowledgeService.select_user_by_id(knowledge_id)
                except ValueError:
                    raise HTTPException(status_code=403, detail="知识库不可用或无权访问") from None
                if owner not in (user_id, SystemUser):
                    raise HTTPException(status_code=403, detail="知识库不可用或无权访问")
            skill_ids = agent.get("agent_skill_ids") or []
            skills = await AgentSkillDao.get_agent_skills_by_ids(skill_ids)
            if ({item.id for item in skills} != set(skill_ids)
                    or any(item.user_id not in (user_id, SystemUser) for item in skills)):
                raise HTTPException(status_code=403, detail="技能不可用或无权访问")
        return model, [by_mcp_id[item] for item in config["mcp_servers"]]

    @classmethod
    async def stream(cls, task, user_id, prepared):
        session, config, agent, model, servers = prepared
        contexts = session.get("contexts", []) if session else []
        try:
            if agent:
                async with aclosing(cls._stream_agent(task, user_id, session, config, agent)) as stream:
                    async for event in stream:
                        yield event
                return
            simple_agent = WorkSpaceSimpleAgent(
                model_config={
                    "model": model["model"], "base_url": model["base_url"],
                    "api_key": model["api_key"], "user_id": user_id,
                },
                mcp_configs=[MCPConfig(**server) for server in servers],
                plugins=config["plugins"], user_id=user_id, session_id=task.session_id,
                chat_config=config,
            )
            history = "\n".join(f"query: {item.get('query', '')}, answer: {item.get('answer', '')}" for item in contexts)
            messages = [
                SystemMessage(content=SYSTEM_PROMPT.format(history=history or "无历史对话")),
                HumanMessage(content=task.query),
            ]
            async with aclosing(simple_agent.astream(messages)) as stream:
                async for event in stream:
                    yield event
        except Exception as exc:
            # Provider exceptions may contain URLs, credentials and original user input.
            logger.warning("Daily conversation failed ({})", type(exc).__name__)
            yield {"event": "error", "data": {"message": "回复生成失败，请重试"}}

    @classmethod
    async def _stream_agent(cls, task, user_id, session, config, agent):
        agent_data = copy.deepcopy(agent)
        agent_data.update(user_id=user_id, llm_id=config["model_id"], tool_ids=config["plugins"], mcp_ids=config["mcp_servers"])
        agent_config = AgentConfig(**agent_data)
        set_agent_name_context(agent_config.name)
        chat_agent = GeneralAgent(agent_config)
        await chat_agent.init_agent()
        contexts = session.get("contexts", []) if session else []
        history = []
        from langchain_core.messages import AIMessage
        for item in contexts:
            history.extend([HumanMessage(content=item.get("query", "")), AIMessage(content=item.get("answer", ""))])
        long_memory = None
        # Workspace IDs are client supplied; keep their memory namespace separate
        # from server-generated legacy dialog IDs and from other users.
        memory_run_id = f"workspace:{user_id}:{task.session_id}"
        if agent_config.enable_memory:
            from agentruler.services.memory.client import memory_client
            try:
                memories = await memory_client.search(query=task.query, run_id=memory_run_id)
                long_memory = "\n".join(item.get("memory", "") for item in memories.get("results", []))
            except Exception as exc:
                logger.warning("Daily memory search unavailable ({})", type(exc).__name__)
        system_prompt = build_completion_system_prompt(agent_config.system_prompt.strip() or SYSTEM_PROMPT, None, long_memory)
        answer = ""
        events = []
        async for event in chat_agent.astream([
            SystemMessage(content=system_prompt), *history, HumanMessage(content=task.query),
        ], raise_on_error=True):
            data = event.get("data") or {}
            if event.get("type") == "response_chunk":
                chunk = data.get("chunk", "")
                answer += chunk
                yield {"event": "task_result", "data": {"message": chunk}}
            elif event.get("type") == "event":
                status = data.get("status", "START")
                safe_event = {
                    "title": data.get("title", "智能体任务"), "status": status,
                    "message": {"START": "正在执行", "END": "执行完成", "ERROR": "工具执行失败"}.get(status, "正在执行"),
                }
                events.append(safe_event)
                yield {"event": "agent_event", "data": safe_event}
        if not answer:
            raise ValueError("Empty agent response")
        context = WorkSpaceSessionContext(query=task.query, answer=answer, config=config, agent_events=events)
        if session:
            await WorkSpaceSessionService.update_workspace_session_contexts(task.session_id, context.model_dump(), user_id=user_id)
        else:
            await WorkSpaceSessionService.create_workspace_session(WorkSpaceSessionCreate(
                title=task.query.strip()[:40], agent="simple", user_id=user_id,
                session_id=task.session_id, contexts=[context.model_dump()],
            ))
        if agent_config.enable_memory:
            try:
                await memory_client.add(messages=[{"role": "user", "content": task.query}, {"role": "assistant", "content": answer}], run_id=memory_run_id)
            except Exception as exc:
                logger.warning("Daily memory save unavailable ({})", type(exc).__name__)
