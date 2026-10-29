from fastapi import APIRouter, Depends, Query, HTTPException
from agentruler.api.services.history import HistoryService
from agentruler.api.services.dialog import DialogService
from agentruler.api.services.user import get_login_user, UserPayload
from agentruler.api.responses.builder import resp_200, resp_500, UnifiedResponseModel
from loguru import logger

router = APIRouter(tags=["History"])

@router.get("/history", response_model=UnifiedResponseModel)
async def get_dialog_history(dialog_id: str = Query(..., description="对话的ID", embed=True),
                             login_user: UserPayload = Depends(get_login_user)):
    try:
        await DialogService.verify_user_permission(dialog_id, login_user.user_id)
        results = await HistoryService.get_dialog_history(dialog_id=dialog_id)
        return resp_200(data=results)
    except HTTPException:
        raise
    except Exception as err:
        logger.error(err)
        return resp_500(message=str(err))
