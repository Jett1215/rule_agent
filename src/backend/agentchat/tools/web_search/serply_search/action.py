from langchain.tools import tool
import requests
from urllib.parse import urlencode

from agentchat.settings import app_settings


@tool("serply_search", parse_docstring=True)
def serply_search(query: str, count: int = 10) -> str:
    """
    使用 Serply Search API 进行网页搜索。

    Args:
        query (str): 用户的搜索词（必填）
        count (int): 返回结果条数，范围 1-50，默认 10

    Returns:
        str: 格式化的搜索结果或错误信息
    """
    count = min(max(count, 1), 50)
    api_key = app_settings.tools.serply.get("api_key")
    path = urlencode({"q": query, "num": count})
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json",
        # Serply 位于 Cloudflare 之后，默认的 requests User-Agent 会被拦截，需显式指定
        "User-Agent": "AgentChat",
    }

    response = requests.get(f"https://api.serply.io/v1/search/{path}", headers=headers)

    if response.status_code == 200:
        try:
            results = response.json().get("results") or []
            if not results:
                return "未找到相关结果。"
            formatted_results = ""
            for idx, item in enumerate(results[:count], start=1):
                formatted_results += (
                    f"引用: {idx}\n"
                    f"标题: {item.get('title', '')}\n"
                    f"URL: {item.get('link', '')}\n"
                    f"摘要: {item.get('description', '')}\n\n"
                )
            return formatted_results.strip()
        except Exception as e:
            return f"搜索API请求失败，原因是：搜索结果解析失败 {str(e)}"
    else:
        return f"搜索API请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
