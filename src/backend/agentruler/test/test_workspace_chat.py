"""Daily chat contracts, isolated from databases, providers and application startup."""

import asyncio
import copy
import importlib.util
import json
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel

from agentruler.schemas.workspace import WorkSpaceSimpleTask


ROOT = Path(__file__).parents[1]


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    return result


def load_source(name, relative_path, boundaries):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    result = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, boundaries):
        spec.loader.exec_module(result)
    return result


MODELS = load_source("isolated_workspace_models", "database/models/workspace_session.py", {
    "agentruler.database.models.base": module("agentruler.database.models.base", SQLModelSerializable=SQLModel),
})


class WorkspaceChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session_service = SimpleNamespace(
            get_workspace_session_from_id=AsyncMock(return_value=None),
            create_workspace_session=AsyncMock(), update_workspace_session_contexts=AsyncMock(),
            delete_workspace_session=AsyncMock(), get_workspace_sessions=AsyncMock(return_value=[]),
        )
        self.model = {"llm_id": "model", "model": "test-model", "llm_type": "LLM", "user_id": "user", "base_url": "https://provider.invalid", "api_key": "fixture-secret"}
        self.agent = {"id": "agent", "name": "Assistant", "user_id": "user", "llm_id": "model", "tool_ids": ["tool"], "mcp_ids": ["mcp"], "knowledge_ids": ["knowledge"], "agent_skill_ids": ["skill"], "system_prompt": "Custom assistant instructions", "enable_memory": False}
        self.agent_service = SimpleNamespace(select_agent_by_id=AsyncMock(return_value=self.agent))
        self.llm_service = SimpleNamespace(get_llm_by_id=AsyncMock(return_value=self.model))
        self.tools_service = SimpleNamespace(get_visible_tool_by_user=AsyncMock(return_value=[{"tool_id": "tool"}]))
        self.mcp_service = SimpleNamespace(get_all_servers=AsyncMock(return_value=[{"mcp_server_id": "mcp", "server_name": "MCP", "type": "sse", "url": "https://mcp.invalid"}]))
        self.knowledge_service = SimpleNamespace(select_user_by_id=AsyncMock(return_value="user"))
        self.skill_dao = SimpleNamespace(get_agent_skills_by_ids=AsyncMock(return_value=[SimpleNamespace(id="skill", user_id="user")]))
        self.general = SimpleNamespace(init_agent=AsyncMock())

        async def general_stream(messages, **kwargs):
            yield {"type": "event", "data": {"title": "Execute tool", "status": "START", "message": "fixture-secret"}}
            yield {"type": "response_chunk", "data": {"chunk": "answer"}}

        self.general.astream = Mock(side_effect=general_stream)
        self.general_factory = Mock(return_value=self.general)
        self.simple = SimpleNamespace()

        async def simple_stream(messages):
            yield {"event": "task_result", "data": {"message": "plain answer"}}

        self.simple.astream = Mock(side_effect=simple_stream)
        self.simple_factory = Mock(return_value=self.simple)
        self.memory = SimpleNamespace(search=AsyncMock(return_value={"results": [{"memory": "Remembered preference"}]}), add=AsyncMock())
        self.boundaries = {
            "agentruler.api.services.agent": module("agentruler.api.services.agent", AgentService=self.agent_service),
            "agentruler.api.services.knowledge": module("agentruler.api.services.knowledge", KnowledgeService=self.knowledge_service),
            "agentruler.api.services.llm": module("agentruler.api.services.llm", LLMService=self.llm_service),
            "agentruler.api.services.mcp_server": module("agentruler.api.services.mcp_server", MCPService=self.mcp_service),
            "agentruler.api.services.tool": module("agentruler.api.services.tool", ToolService=self.tools_service),
            "agentruler.api.services.workspace_session": module("agentruler.api.services.workspace_session", WorkSpaceSessionService=self.session_service),
            "agentruler.core.agents.general_agent": module("agentruler.core.agents.general_agent", AgentConfig=SimpleNamespace, GeneralAgent=self.general_factory),
            "agentruler.database.dao.agent_skill": module("agentruler.database.dao.agent_skill", AgentSkillDao=self.skill_dao),
            "agentruler.database.models.user": module("agentruler.database.models.user", SystemUser="0", AdminUser="1"),
            "agentruler.database.models.workspace_session": MODELS,
            "agentruler.services.workspace.simple_agent": module("agentruler.services.workspace.simple_agent", WorkSpaceSimpleAgent=self.simple_factory, MCPConfig=SimpleNamespace),
            "agentruler.utils.contexts": module("agentruler.utils.contexts", set_agent_name_context=lambda value: None, set_user_id_context=lambda value: None),
            "agentruler.schemas.usage_stats": module("agentruler.schemas.usage_stats", UsageStatsAgentType=SimpleNamespace(simple_agent="simple")),
            "agentruler.utils.helpers": module("agentruler.utils.helpers", build_completion_system_prompt=lambda prompt, summary, memory: prompt.replace("{history}", str(summary)) + (memory or "")),
            "agentruler.services.memory.client": module("agentruler.services.memory.client", memory_client=self.memory),
        }
        self.service_module = load_source("isolated_workspace_chat", "api/services/workspace_chat.py", self.boundaries)
        self.service = self.service_module.WorkspaceChatService

    def task(self, **values):
        return WorkSpaceSimpleTask(query="question", session_id="session", **values)

    async def collect(self, task):
        prepared = await self.service.prepare(task, "user")
        with patch.dict(sys.modules, self.boundaries):
            return [event async for event in self.service.stream(task, "user", prepared)]

    async def test_agent_defaults_preserve_definition_and_save_configuration(self):
        before = copy.deepcopy(self.agent)
        events = await self.collect(self.task(agent_id="agent"))
        self.assertEqual(self.agent, before)
        config = self.general_factory.call_args.args[0]
        self.assertEqual((config.llm_id, config.tool_ids, config.mcp_ids), ("model", ["tool"], ["mcp"]))
        self.assertEqual(config.knowledge_ids, ["knowledge"])
        self.assertEqual(config.agent_skill_ids, ["skill"])
        self.assertIn("Custom assistant instructions", self.general.astream.call_args.args[0][0].content)
        self.assertTrue(self.general.astream.call_args.kwargs["raise_on_error"])
        self.assertNotIn("fixture-secret", json.dumps(events))
        saved = self.session_service.create_workspace_session.await_args.args[0]
        self.assertEqual(saved.agent, "simple")
        self.assertEqual(saved.contexts[0]["config"], {"agent_id": "agent", "model_id": "model", "plugins": ["tool"], "mcp_servers": ["mcp"]})
        self.assertEqual(saved.contexts[0]["answer"], "answer")

    async def test_empty_lists_clear_agent_tools_and_mcp(self):
        await self.collect(self.task(agent_id="agent", plugins=[], mcp_servers=[]))
        config = self.general_factory.call_args.args[0]
        self.assertEqual(config.tool_ids, [])
        self.assertEqual(config.mcp_ids, [])
        self.assertEqual(self.agent["tool_ids"], ["tool"])

    async def test_restored_configuration_and_history_are_used(self):
        config = {"agent_id": "agent", "model_id": "model", "plugins": [], "mcp_servers": []}
        self.session_service.get_workspace_session_from_id.return_value = {"agent": "simple", "contexts": [{"query": "previous", "answer": "response", "config": config}]}
        await self.collect(self.task())
        saved = self.session_service.update_workspace_session_contexts.await_args.args[1]
        self.assertEqual(saved["config"], config)
        messages = self.general.astream.call_args.args[0]
        self.assertEqual([item.content for item in messages[1:]], ["previous", "response", "question"])

    async def test_explicit_generic_assistant_clears_previous_agent(self):
        self.session_service.get_workspace_session_from_id.return_value = {"agent": "simple", "contexts": [{"config": {"agent_id": "agent", "model_id": "model", "plugins": ["tool"], "mcp_servers": ["mcp"]}}]}
        await self.collect(self.task(agent_id=None, model_id="model", plugins=[], mcp_servers=[]))
        self.general_factory.assert_not_called()
        self.assertEqual(self.simple_factory.call_args.kwargs["chat_config"]["agent_id"], None)

    async def test_generic_assistant_retains_compatible_stream_and_config(self):
        events = await self.collect(self.task(model_id="model", plugins=["tool"], mcp_servers=["mcp"]))
        self.assertEqual(events, [{"event": "task_result", "data": {"message": "plain answer"}}])
        self.assertEqual(self.simple_factory.call_args.kwargs["chat_config"]["plugins"], ["tool"])

    async def test_private_dependencies_are_rejected_before_agent_execution(self):
        cases = [(self.agent_service.select_agent_by_id, {**self.agent, "user_id": "other"}),
                 (self.llm_service.get_llm_by_id, {**self.model, "user_id": "other"}),
                 (self.tools_service.get_visible_tool_by_user, []),
                 (self.mcp_service.get_all_servers, []),
                 (self.knowledge_service.select_user_by_id, "other"),
                 (self.skill_dao.get_agent_skills_by_ids, [SimpleNamespace(id="skill", user_id="other")])]
        for dependency, value in cases:
            with self.subTest(dependency=dependency):
                original = dependency.return_value
                dependency.return_value = value
                with self.assertRaises(HTTPException) as error:
                    await self.service.prepare(self.task(agent_id="agent"), "user")
                self.assertEqual(error.exception.status_code, 403)
                dependency.return_value = original
        self.general_factory.assert_not_called()

    async def test_foreign_session_and_wrong_mode_are_rejected(self):
        self.session_service.get_workspace_session_from_id.side_effect = HTTPException(403)
        with self.assertRaises(HTTPException) as error:
            await self.service.prepare(self.task(model_id="model"), "user")
        self.assertEqual(error.exception.status_code, 403)
        self.session_service.get_workspace_session_from_id.side_effect = None
        self.session_service.get_workspace_session_from_id.return_value = {"agent": "lingseek"}
        with self.assertRaises(HTTPException) as error:
            await self.service.prepare(self.task(model_id="model"), "user")
        self.assertEqual(error.exception.status_code, 409)

    async def test_missing_model_and_blank_input_are_validation_errors(self):
        for task in (self.task(), WorkSpaceSimpleTask(query="  ", session_id="session", model_id="model")):
            with self.assertRaises(HTTPException) as error:
                await self.service.prepare(task, "user")
            self.assertEqual(error.exception.status_code, 422)

    async def test_failed_agent_does_not_save_success_or_leak_provider_error(self):
        async def fail(*args, **kwargs):
            yield {"type": "response_chunk", "data": {"chunk": "partial"}}
            raise RuntimeError("fixture-secret")
        self.general.astream.side_effect = fail
        events = await self.collect(self.task(agent_id="agent"))
        self.assertEqual(events[-1]["event"], "error")
        self.assertNotIn("fixture-secret", json.dumps(events))
        self.session_service.create_workspace_session.assert_not_awaited()
        self.session_service.update_workspace_session_contexts.assert_not_awaited()

    async def test_cancellation_propagates_without_persistence(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        async def wait(*args, **kwargs):
            try:
                started.set()
                await asyncio.Event().wait()
                yield {}
            finally:
                cancelled.set()
        self.general.astream.side_effect = wait
        task = asyncio.create_task(self.collect(self.task(agent_id="agent")))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())
        self.session_service.create_workspace_session.assert_not_awaited()

    async def test_memory_is_scoped_to_session_and_does_not_change_agent(self):
        self.agent["enable_memory"] = True
        await self.collect(self.task(agent_id="agent"))
        self.memory.search.assert_awaited_once_with(query="question", run_id="workspace:user:session")
        self.assertEqual(self.memory.add.await_args.kwargs["run_id"], "workspace:user:session")

    async def test_legacy_owned_dialog_rejects_private_agent_and_revoked_dependencies(self):
        async def login():
            return SimpleNamespace(user_id="user")
        dialog = SimpleNamespace(verify_user_permission=AsyncMock(), get_agent_by_dialog_id=AsyncMock(return_value=self.agent))
        history = SimpleNamespace(save_chat_history=AsyncMock())
        boundaries = {**self.boundaries,
            "agentruler.api.services.workspace_chat": self.service_module,
            "agentruler.api.services.dialog": module("agentruler.api.services.dialog", DialogService=dialog),
            "agentruler.api.services.history": module("agentruler.api.services.history", HistoryService=history),
            "agentruler.api.services.user": module("agentruler.api.services.user", UserPayload=SimpleNamespace, get_login_user=login),
            "agentruler.utils.common": module("agentruler.utils.common", count_tokens_usage=lambda value: 1),
            "agentruler.utils.helpers": module("agentruler.utils.helpers", build_completion_system_prompt=lambda *values: "", build_completion_user_input=lambda **values: ""),
        }
        route = load_source("isolated_legacy_completion_resources", "api/v1/completion.py", boundaries)
        app = FastAPI()
        app.include_router(route.router, prefix="/api/v1")
        cases = [
            (dialog.get_agent_by_dialog_id, {**self.agent, "user_id": "other"}),
            (self.llm_service.get_llm_by_id, {**self.model, "user_id": "other"}),
            (self.tools_service.get_visible_tool_by_user, []),
            (self.mcp_service.get_all_servers, []),
            (self.knowledge_service.select_user_by_id, "other"),
            (self.skill_dao.get_agent_skills_by_ids, [SimpleNamespace(id="skill", user_id="other")]),
        ]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for dependency, value in cases:
                with self.subTest(dependency=dependency):
                    original = dependency.return_value
                    dependency.return_value = value
                    response = await client.post("/api/v1/completion", json={"dialog_id": "owned-dialog", "user_input": "question"})
                    self.assertEqual(response.status_code, 403)
                    dependency.return_value = original
        self.general_factory.assert_not_called()
        history.save_chat_history.assert_not_awaited()

    async def test_legacy_empty_model_keeps_system_default_compatibility(self):
        await self.service.validate_agent_resources({**self.agent, "llm_id": ""}, "user")
        self.llm_service.get_llm_by_id.assert_not_awaited()

    async def test_closing_response_closes_the_nested_daily_stream(self):
        async def login():
            return SimpleNamespace(user_id="user")
        boundaries = {**self.boundaries,
            "agentruler.api.services.workspace_chat": self.service_module,
            "agentruler.api.services.user": module("agentruler.api.services.user", UserPayload=SimpleNamespace, get_login_user=login),
        }
        route = load_source("isolated_workspace_close", "api/v1/workspace.py", boundaries)
        closed = asyncio.Event()
        async def stream(messages):
            try:
                yield {"event": "task_result", "data": {"message": "partial"}}
                await asyncio.Event().wait()
            finally:
                closed.set()
        self.simple.astream.side_effect = stream
        response = await route.workspace_simple_chat(self.task(model_id="model"), await login())
        await anext(response.body_iterator)
        await response.body_iterator.aclose()
        self.assertTrue(closed.is_set())

    async def test_http_endpoint_preserves_errors_and_sse_contract(self):
        async def login():
            return SimpleNamespace(user_id="user")
        boundaries = {**self.boundaries,
            "agentruler.api.services.workspace_chat": self.service_module,
            "agentruler.api.services.user": module("agentruler.api.services.user", UserPayload=SimpleNamespace, get_login_user=login),
        }
        route = load_source("isolated_workspace_route", "api/v1/workspace.py", boundaries)
        app = FastAPI()
        app.include_router(route.router, prefix="/api/v1")
        with patch.dict(sys.modules, self.boundaries):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/workspace/simple/chat", json=self.task(agent_id="agent").model_dump(exclude_unset=True))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
                self.assertIn('"event": "task_result"', response.text)
                self.assertIn('"event": "done"', response.text)
                async def fail(*args, **kwargs):
                    raise RuntimeError("fixture-secret")
                    yield {}
                self.general.astream.side_effect = fail
                response = await client.post("/api/v1/workspace/simple/chat", json=self.task(agent_id="agent").model_dump(exclude_unset=True))
                self.assertIn('"event": "error"', response.text)
                self.assertNotIn('"event": "done"', response.text)
                self.assertNotIn("fixture-secret", response.text)
                self.session_service.get_workspace_session_from_id.side_effect = HTTPException(403, "Forbidden")
                for path, method, payload in [
                    ("/api/v1/workspace/simple/chat", client.post, {"json": self.task(model_id="model").model_dump()}),
                    ("/api/v1/workspace/session/session", client.post, {}),
                    ("/api/v1/workspace/session?session_id=session", client.delete, {}),
                ]:
                    response = await method(path, **payload)
                    self.assertEqual(response.status_code, 403)


class SessionOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_append_checks_current_owner_under_row_lock(self):
        row = SimpleNamespace(user_id="new-owner", contexts=[])
        session = SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(first=lambda: row)), commit=AsyncMock(), refresh=AsyncMock())
        @asynccontextmanager
        async def getter():
            yield session
        dao = load_source("isolated_workspace_dao", "database/dao/workspace_session.py", {
            "agentruler.database.session": module("agentruler.database.session", session_getter=None, async_session_getter=getter),
            "agentruler.database.models.workspace_session": MODELS,
        }).WorkSpaceSessionDao
        with self.assertRaises(PermissionError):
            await dao.update_workspace_session_contexts("reused-id", {"answer": "old-owner-answer"}, user_id="old-owner")
        self.assertEqual(row.contexts, [])
        session.commit.assert_not_awaited()
        self.assertIsNotNone(session.exec.await_args.args[0]._for_update_arg)
        await dao.update_workspace_session_contexts("reused-id", {"answer": "new-answer"}, user_id="new-owner")
        self.assertEqual(row.contexts, [{"answer": "new-answer"}])
        session.commit.assert_awaited_once()

    async def test_workspace_service_enforces_owner_for_existing_records(self):
        dao = SimpleNamespace(get_workspace_session_from_id=AsyncMock(return_value=SimpleNamespace(user_id="owner", to_dict=lambda: {"session_id": "id"})))
        service = load_source("isolated_workspace_session", "api/services/workspace_session.py", {
            "agentruler.database.dao.workspace_session": module("agentruler.database.dao.workspace_session", WorkSpaceSession=object, WorkSpaceSessionDao=dao),
            "agentruler.database.models.workspace_session": MODELS,
        }).WorkSpaceSessionService
        self.assertEqual(await service.get_workspace_session_from_id("id", "owner"), {"session_id": "id"})
        for user_id in ("other", "1"):
            with self.assertRaises(HTTPException) as error:
                await service.get_workspace_session_from_id("id", user_id)
            self.assertEqual(error.exception.status_code, 403)
        dao.get_workspace_session_from_id.return_value = None
        self.assertIsNone(await service.get_workspace_session_from_id("missing", "owner"))

    async def test_legacy_history_completion_and_deletion_require_owner(self):
        dao = SimpleNamespace(get_agent_by_dialog_id=AsyncMock(return_value=SimpleNamespace(user_id="owner", agent_id="agent")))
        agent_service = SimpleNamespace(select_agent_by_id=AsyncMock(return_value={"name": "Agent name", "logo_url": "logo", "update_time": "future", "user_id": "agent-owner"}))
        boundaries = {
            "agentruler.api.services.agent": module("agentruler.api.services.agent", AgentService=agent_service),
            "agentruler.core.callbacks": module("agentruler.core.callbacks", usage_metadata_callback=None),
            "agentruler.core.models.manager": module("agentruler.core.models.manager", ModelManager=object),
            "agentruler.database.dao.dialog": module("agentruler.database.dao.dialog", DialogDao=dao),
            "agentruler.database.dao.history": module("agentruler.database.dao.history", HistoryDao=object),
            "agentruler.database.models.user": module("agentruler.database.models.user", AdminUser="1"),
        }
        service = load_source("isolated_dialog_service", "api/services/dialog.py", boundaries).DialogService
        service.delete_dialog = AsyncMock()
        service.get_list_dialog = AsyncMock(return_value=[])
        history_service = SimpleNamespace(get_dialog_history=AsyncMock(return_value=[]))
        async def login():
            return SimpleNamespace(user_id="other")
        general_factory = Mock()
        boundaries.update({
            "agentruler.api.services.dialog": module("agentruler.api.services.dialog", DialogService=service),
            "agentruler.api.services.workspace_chat": module("agentruler.api.services.workspace_chat", WorkspaceChatService=SimpleNamespace(validate_agent_resources=AsyncMock())),
            "agentruler.api.services.history": module("agentruler.api.services.history", HistoryService=history_service),
            "agentruler.api.services.user": module("agentruler.api.services.user", UserPayload=SimpleNamespace, get_login_user=login),
            "agentruler.core.agents.general_agent": module("agentruler.core.agents.general_agent", AgentConfig=SimpleNamespace, GeneralAgent=general_factory),
            "agentruler.services.memory.client": module("agentruler.services.memory.client", memory_client=object),
            "agentruler.utils.common": module("agentruler.utils.common", count_tokens_usage=lambda value: 1),
            "agentruler.utils.contexts": module("agentruler.utils.contexts", set_user_id_context=lambda value: None, set_agent_name_context=lambda value: None),
            "agentruler.utils.helpers": module("agentruler.utils.helpers", build_completion_system_prompt=lambda *values: "", build_completion_user_input=lambda **values: ""),
        })
        app = FastAPI()
        for name in ("history", "completion", "dialog"):
            route = load_source(f"isolated_legacy_{name}", f"api/v1/{name}.py", boundaries)
            app.include_router(route.router, prefix="/api/v1")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for user_id, expected in (("other", 403), ("1", 403)):
                async def user():
                    return SimpleNamespace(user_id=user_id)
                app.dependency_overrides[login] = user
                responses = [
                    await client.get("/api/v1/history", params={"dialog_id": "dialog"}),
                    await client.post("/api/v1/completion", json={"dialog_id": "dialog", "user_input": "question"}),
                    await client.request("DELETE", "/api/v1/dialog", json={"dialog_id": "dialog"}),
                ]
                self.assertEqual([response.status_code for response in responses], [expected] * 3)
            general_factory.assert_not_called()
            history_service.get_dialog_history.assert_not_awaited()
            service.delete_dialog.assert_not_awaited()
            dao.get_agent_by_dialog_id.return_value = None
            missing = await client.get("/api/v1/history", params={"dialog_id": "missing"})
            self.assertEqual(missing.status_code, 404)
            dao.get_agent_by_dialog_id.return_value = SimpleNamespace(user_id="other")
            app.dependency_overrides.clear()
            owner = await client.get("/api/v1/history", params={"dialog_id": "dialog"})
            self.assertEqual(owner.status_code, 200)
            removed = await client.request("DELETE", "/api/v1/dialog", json={"dialog_id": "dialog"})
            self.assertEqual(removed.status_code, 200)
            service.delete_dialog.assert_awaited_once_with(dialog_id="dialog")
            service.get_list_dialog.return_value = [{"dialog_id": "dialog", "agent_id": "agent", "name": "Saved dialog title", "update_time": "saved-time", "user_id": "other"}]
            listed = (await client.get("/api/v1/dialog/list")).json()["data"][0]
            self.assertEqual((listed["name"], listed["update_time"], listed["user_id"]), ("Saved dialog title", "saved-time", "other"))
            self.assertEqual(listed["agent_name"], "Agent name")
            agent_service.select_agent_by_id.return_value = None
            self.assertEqual(len((await client.get("/api/v1/dialog/list")).json()["data"]), 1)


class SimpleDailyPersistenceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from agentruler.test.test_jev_workspace import _load_workspace_module
        cls.workspace = _load_workspace_module()
        cls.workspace.WorkSpaceSessionContext = MODELS.WorkSpaceSessionContext
        cls.workspace.WorkSpaceSessionCreate = MODELS.WorkSpaceSessionCreate

    def setUp(self):
        from langchain_core.messages import AIMessageChunk, HumanMessage
        self.messages = [HumanMessage(content="question")]
        self.service = SimpleNamespace(get_workspace_session_from_id=AsyncMock(return_value=None), create_workspace_session=AsyncMock(), update_workspace_session_contexts=AsyncMock())
        self.patch = patch.object(self.workspace, "WorkSpaceSessionService", self.service)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.agent = self.workspace.WorkSpaceSimpleAgent.__new__(self.workspace.WorkSpaceSimpleAgent)
        self.agent._initialized = True
        self.agent._tool_event_queue = None
        self.agent.tools = []
        self.agent.user_id = "user"
        self.agent.session_id = "session"
        self.agent.chat_config = {"agent_id": None, "model_id": "model", "plugins": [], "mcp_servers": []}
        self.agent._generate_title = AsyncMock(return_value="Title")
        async def stream(**kwargs):
            yield AIMessageChunk(content="answer")
        self.agent.model = SimpleNamespace(astream=Mock(side_effect=stream))

    async def test_actual_simple_stream_saves_configuration_in_existing_json(self):
        events = [event async for event in self.agent.astream(self.messages)]
        self.assertEqual(events[-1]["data"]["message"], "answer")
        saved = self.service.create_workspace_session.await_args.args[0]
        self.assertEqual(saved.contexts[0]["config"], self.agent.chat_config)
        self.assertEqual(saved.contexts[0]["answer"], "answer")
        self.service.get_workspace_session_from_id.return_value = {"title": "Title"}
        await self.agent._add_workspace_session("Title", MODELS.WorkSpaceSessionContext(query="next", answer="response", config=self.agent.chat_config))
        self.assertEqual(self.service.update_workspace_session_contexts.await_args.kwargs["session_context"]["config"], self.agent.chat_config)

    async def test_closing_simple_stream_cancels_background_title_and_does_not_save(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def title(query):
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        self.agent._generate_title = title
        stream = self.agent.astream(self.messages)
        await anext(stream)
        await started.wait()
        await stream.aclose()
        self.assertTrue(cancelled.is_set())
        self.service.create_workspace_session.assert_not_awaited()

    async def test_mcp_visible_arguments_keep_fixed_query_and_redact_nested_secrets(self):
        self.agent.mcp_configs = [SimpleNamespace(server_name="MCP", url="http://127.0.0.1/mcp/63742310-275b-4c7f-87d0-2ff107948ca0")]
        dao = SimpleNamespace(get_tool_by_name=AsyncMock(return_value=SimpleNamespace(api_info={"base_url": "https://provider.invalid", "path": "/weather?current=temperature"})))
        arguments = {"latitude": 1, "api_key": "secret", "nested": {"token": "secret"}}
        with patch.dict(sys.modules, {"agentruler.database.dao.register_mcp": module("agentruler.database.dao.register_mcp", RegisterMcpDao=dao)}):
            visible = await self.agent._get_visible_mcp_arguments("MCP", "weather", arguments)
        self.assertEqual(visible, {"latitude": 1, "api_key": "***", "nested": {"token": "***"}, "current": "temperature"})
        self.assertEqual(arguments["api_key"], "secret")
        self.assertEqual(arguments["nested"]["token"], "secret")


class GeneralAgentStrictStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_strict_mode_propagates_errors_and_legacy_fallback_remains(self):
        dependencies = {
            "agentruler.api.services.agent_skill": {"AgentSkillService": object},
            "agentruler.core.agents.skill_agent": {"SkillAgent": object},
            "agentruler.core.callbacks": {"usage_metadata_callback": None},
            "agentruler.database": {"AgentSkill": object},
            "agentruler.tools": {"AgentToolsWithName": {}},
            "agentruler.api.services.llm": {"LLMService": object},
            "agentruler.core.models.manager": {"ModelManager": object},
            "agentruler.api.services.tool": {"ToolService": object},
            "agentruler.services.rag.handler": {"RagHandler": object},
            "agentruler.core.agents.mcp_agent": {"MCPAgent": object, "MCPConfig": object},
            "agentruler.api.services.mcp_server": {"MCPService": object},
            "agentruler.tools.openapi_tool.adapter": {"OpenAPIToolAdapter": object},
        }
        production = load_source("isolated_general_agent", "core/agents/general_agent.py", {
            name: module(name, **attributes) for name, attributes in dependencies.items()
        })
        agent = production.GeneralAgent.__new__(production.GeneralAgent)
        agent.agent_config = SimpleNamespace(user_id="user")
        async def fail(**kwargs):
            raise RuntimeError("simulated provider failure")
            yield None
        agent.react_agent = SimpleNamespace(astream=Mock(side_effect=fail))
        with self.assertRaises(RuntimeError):
            [event async for event in agent.astream([], raise_on_error=True)]
        legacy = [event async for event in agent.astream([])]
        self.assertEqual(legacy[0]["type"], "response_chunk")
        self.assertIn("知识盲区", legacy[0]["data"]["chunk"])


if __name__ == "__main__":
    unittest.main()
