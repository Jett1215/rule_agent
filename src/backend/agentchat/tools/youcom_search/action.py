from typing import Optional, Literal
import requests

from langchain.tools import tool

from agentchat.settings import app_settings

YOUCOM_SEARCH_URL = "https://ydc-index.io/v1/search"


def _youcom_search(query: str, max_results: int = 10) -> str:
    """使用 You.com Search API 进行网页搜索"""
    api_key = app_settings.tools.youcom.get("api_key", "").strip()
    if not api_key:
        return "You.com Search API 未配置 YOUCOM_API_KEY"

    headers = {
        "Accept": "application/json",
        "X-API-Key": api_key,
    }
    payload = {"query": query, "count": min(max(max_results, 1), 20)}

    try:
        response = requests.post(
            YOUCOM_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
    except Exception as e:
        return f"You.com Search 请求失败: {e}"

    if response.status_code == 429:
        return "You.com Search 请求频率超限 (429)"
    if response.status_code == 401:
        return "You.com API Key 无效或已过期"
    if response.status_code == 403:
        return "You.com API Key 权限不足"
    if response.status_code != 200:
        return f"You.com Search 请求失败 (Status {response.status_code})"

    try:
        data = response.json()
    except Exception:
        return "You.com Search 返回非 JSON 响应"

    web_results = data.get("results", {}).get("web", [])
    if not isinstance(web_results, list):
        web_results = data.get("results", [])

    if not web_results:
        return "未找到相关结果"

    lines = []
    for i, item in enumerate(web_results, 1):
        title = item.get("title", f"结果 {i}")
        url = item.get("url", "")
        snippets = item.get("snippets", [])
        snippet = snippets[0] if isinstance(snippets, list) and snippets else item.get("description", "")
        lines.append(f"[{i}] {title}\n   网址: {url}\n   摘要: {snippet}")

    return "\n\n".join(lines)


@tool("youcom_search", parse_docstring=True)
def youcom_search(
    query: str,
    max_results: Optional[int] = 10,
):
    """
    使用 You.com Search API 进行联网搜索。

    Args:
        query: 用户想要搜索的问题
        max_results: 最大返回结果数量，默认 10

    Returns:
        将联网搜索到的信息格式化后返回给用户
    """
    return _youcom_search(query, max_results=max_results)
