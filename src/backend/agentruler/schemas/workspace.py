from enum import Enum
from typing import List
from pydantic import BaseModel, Field

class WorkSpaceAgents(Enum):
    LingSeekAgent: str = "lingseek"

    SimpleAgent: str = "simple"

    WeChatAgent: str = "wechat-agent"


class WorkSpaceSimpleTask(BaseModel):
    query: str = Field(min_length=1)
    model_id: str | None = None
    session_id: str = Field(min_length=1, max_length=128)
    plugins: List[str] | None = None
    mcp_servers: List[str] | None = None
    agent_id: str | None = None
