import json
from contextlib import aclosing
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from agentruler.api.services.tool import ToolService
from agentruler.api.services.workspace_session import WorkSpaceSessionService
from agentruler.api.services.workspace_chat import WorkspaceChatService
from agentruler.api.responses.builder import resp_200
from agentruler.schemas.usage_stats import UsageStatsAgentType
from agentruler.schemas.workspace import WorkSpaceSimpleTask
from agentruler.api.services.user import UserPayload, get_login_user
from agentruler.utils.contexts import set_user_id_context, set_agent_name_context

router = APIRouter(prefix="/workspace", tags=["WorkSpace"])


@router.get("/plugins", summary="获取工作台的可用插件")
async def get_workspace_plugins(login_user: UserPayload = Depends(get_login_user)):
    results = await ToolService.get_visible_tool_by_user(login_user.user_id)
    return resp_200(data=results)

@router.get("/session", summary="获取工作台所有会话列表")
async def get_workspace_sessions(login_user: UserPayload = Depends(get_login_user)):
    results = await WorkSpaceSessionService.get_workspace_sessions(login_user.user_id)
    return resp_200(data=results)


@router.post("/session", summary="创建工作台会话")
async def create_workspace_session(*,
                                   title: str = "",
                                   contexts: dict = {},
                                   login_user: UserPayload = Depends(get_login_user)):
    pass

@router.post("/session/{session_id}", summary="进入工作台会话")
async def workspace_session_info(session_id: str,
                                 login_user: UserPayload = Depends(get_login_user)):
    result = await WorkSpaceSessionService.get_workspace_session_from_id(session_id, login_user.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return resp_200(data=result)

@router.delete("/session", summary="删除工作台的会话")
async def create_workspace_session(session_id: str,
                                   login_user: UserPayload = Depends(get_login_user)):
    result = await WorkSpaceSessionService.get_workspace_session_from_id(session_id, login_user.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    await WorkSpaceSessionService.delete_workspace_session([session_id], login_user.user_id)
    return resp_200()


@router.post("/simple/chat", summary="工作台日常对话")
async def workspace_simple_chat(simple_task: WorkSpaceSimpleTask,
                                login_user: UserPayload = Depends(get_login_user)):
    # 设置全局变量统计调用
    set_user_id_context(login_user.user_id)
    set_agent_name_context(UsageStatsAgentType.simple_agent)

    prepared = await WorkspaceChatService.prepare(simple_task, login_user.user_id)

    async def general_generate():
        failed = False
        async with aclosing(WorkspaceChatService.stream(simple_task, login_user.user_id, prepared)) as stream:
            async for chunk in stream:
                # chunk 已经是 dict: {"event": "task_result", "data": {"message": "..."}}
                # 需要 JSON 序列化后作为 SSE 的 data 字段
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                failed = failed or chunk.get("event") == "error"
        if not failed:
            yield f"data: {json.dumps({'event': 'done', 'data': {'session_id': simple_task.session_id}})}\n\n"

    return StreamingResponse(
        general_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


