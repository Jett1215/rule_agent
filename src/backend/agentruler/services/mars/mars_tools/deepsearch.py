import time
from typing import Optional
from langchain.tools import tool
from langgraph.config import get_stream_writer
from langchain_core.messages import HumanMessage
from agentruler.services.deepsearch.stream_graph import StreamingGraph

@tool(parse_docstring=True)
async def deep_search(user_input: str, user_id: Optional[str] = None):
    """
     执行深度搜索，处理用户查询并返回深度搜索后的结果

    Args:
        user_input: 用户的搜索的信息
        user_id: 当前用户ID，默认为None

    Returns:
        返回深度搜索后的信息
    """
    writer = get_stream_writer()
    messages = [HumanMessage(content=user_input)]

    stream_graph = StreamingGraph()

    async for chunk in stream_graph.run_with_streaming(messages):
        chunk_type = chunk.get('type', 'unknown')
        node = chunk.get('node', 'unknown')
        content = chunk.get('content', '')

        event_data = {
            "type": "response_chunk",
            "time": time.time(),
            "data": ""
        }
        if chunk_type == "streaming":
            event_data["data"] = content
        elif chunk_type in ["start", "complete", "error"]:
            emoji = {"start": "🚀", "complete": "✅", "error": "❌"}[chunk_type]
            event_data["data"] = f"\n #### {emoji} {content}"
        elif chunk_type == "final_result":
            event_data["data"] = f""
        if event_data.get("data"):
            writer(event_data)

