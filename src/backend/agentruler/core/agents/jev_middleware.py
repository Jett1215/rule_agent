"""Filter the tools presented to a model without changing executable tools."""

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.tools import BaseTool
from loguru import logger

from agentruler.services.decision.jev import JevDecisionService


class JevToolSelectorMiddleware(AgentMiddleware):
    """Reconsider tool candidates for each model call, including after tool results."""

    def __init__(self, decision_service: JevDecisionService | None = None):
        super().__init__()
        self.decision_service = decision_service or JevDecisionService()

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # Provider-native tools cannot be represented by the decision service.
        # Keep the whole request intact rather than dropping an unknown tool type.
        if request.tools and all(isinstance(tool, BaseTool) for tool in request.tools):
            try:
                selected_tools = await self.decision_service.select_tools(
                    request.messages, request.tools
                )
            except Exception as err:
                logger.warning("Jev tool selection fell back: {}", type(err).__name__)
            else:
                if selected_tools is not None:
                    authorized_ids = {id(tool) for tool in request.tools}
                    selected_ids = [id(tool) for tool in selected_tools] if isinstance(selected_tools, list) else []
                    if (
                        isinstance(selected_tools, list)
                        and len(selected_ids) == len(set(selected_ids))
                        and set(selected_ids).issubset(authorized_ids)
                    ):
                        request = request.override(tools=selected_tools)
                    else:
                        logger.warning("Jev tool selection fell back: invalid_candidates")

        return await handler(request)
