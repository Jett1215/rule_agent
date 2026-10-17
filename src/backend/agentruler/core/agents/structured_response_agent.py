from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agentruler.core.callbacks import usage_metadata_callback
from agentruler.core.models.manager import ModelManager


class StructuredResponseAgent:
    def __init__(self, response_format, disable_thinking=False):
        self.response_format = response_format
        self.disable_thinking = disable_thinking
        self.structured_agent = self._create_structured_agent()

    def _create_structured_agent(self):
        return create_agent(
            model=ModelManager.get_conversation_model(disable_thinking=self.disable_thinking),
            response_format=ToolStrategy(self.response_format)
        )

    def get_structured_response(self, messages):
        result = self.structured_agent.invoke(
            input={"messages": messages},
            config={"callbacks": [usage_metadata_callback]}
        )
        return result["structured_response"]