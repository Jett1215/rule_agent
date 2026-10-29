from loguru import logger
from fastapi import APIRouter, Depends, Body, HTTPException
from agentruler.api.services.agent import AgentService
from agentruler.api.services.dialog import DialogService
from agentruler.api.services.user import UserPayload, get_login_user
from agentruler.schemas.dialog import DialogCreateRequest
from agentruler.api.responses.builder import resp_200, resp_500, UnifiedResponseModel

router = APIRouter(tags=["Dialog"])


@router.get("/dialog/list", response_model=UnifiedResponseModel)
async def get_dialog(
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        messages = await DialogService.get_list_dialog(user_id=login_user.user_id)
        results = []

        for message in messages:
            message_agent = await AgentService.select_agent_by_id(
                agent_id=message["agent_id"]
            )
            if message_agent:
                # Agent metadata must not overwrite the dialog's title or timestamps.
                message.update({
                    "agent_name": message_agent.get("name", ""),
                    "logo_url": message_agent.get("logo_url", ""),
                })
            results.append(message)

        return resp_200(data=results)
    except Exception as err:
        logger.error(err)
        return resp_500(message=str(err))


@router.post("/dialog", response_model=UnifiedResponseModel)
async def create_dialog(
    dialog_req: DialogCreateRequest,
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        dialog = await DialogService.create_dialog(
            name=dialog_req.name,
            agent_id=dialog_req.agent_id,
            agent_type=dialog_req.agent_type,
            user_id=login_user.user_id
        )
        return resp_200(dialog)
    except Exception as err:
        logger.error(err)
        return resp_500(message=str(err))


@router.delete("/dialog", response_model=UnifiedResponseModel)
async def delete_dialog(
    dialog_id: str = Body(description="对话ID", embed=True),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        # 验证用户权限
        await DialogService.verify_user_permission(dialog_id, login_user.user_id)

        await DialogService.delete_dialog(dialog_id=dialog_id)
        return resp_200()
    except HTTPException:
        raise
    except Exception as err:
        logger.error(err)
        return resp_500(message=str(err))
