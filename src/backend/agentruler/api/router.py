from fastapi import APIRouter
from agentruler.api.mcp_proxy.router import mcp_proxy_router
from agentruler.api.v1.router import api_v1_router

router = APIRouter()

router.include_router(api_v1_router)
router.include_router(mcp_proxy_router)