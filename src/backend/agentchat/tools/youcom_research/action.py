from typing import Literal
import requests

from langchain.tools import tool

from agentchat.settings import app_settings

YOUCOM_RESEARCH_URL = "https://ydc-index.io/v1/research"


class YoucomResearchEngine:
    """You.com Research API 封装 - 返回 markdown 综述 + 引用来源"""

    def research(self, query: str, research_effort: str = "standard") -> dict:
        """
        调用 You.com Research API 执行深度研究。

        Args:
            query: 研究问题
            research_effort: 研究深度，可选 lite/standard/deep/exhaustive，默认 standard

        Returns:
            包含 content (markdown综述) 和 sources (引用列表) 的字典
        """
        api_key = app_settings.tools.youcom.get("api_key", "").strip()
        if not api_key:
            return {"content": "", "sources": [], "error": "YOUCOM_API_KEY 未配置"}

        allowed = {"lite", "standard", "deep", "exhaustive"}
        if research_effort not in allowed:
            research_effort = "standard"

        headers = {
            "Accept": "application/json",
            "X-API-Key": api_key,
        }
        payload = {"input": query, "research_effort": research_effort}

        try:
            response = requests.post(
                YOUCOM_RESEARCH_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except Exception as e:
            return {"content": "", "sources": [], "error": str(e)}

        if response.status_code == 429:
            return {"content": "", "sources": [], "error": "You.com Research 频率超限 (429)"}
        if response.status_code == 401:
            return {"content": "", "sources": [], "error": "YOUCOM_API_KEY 无效或已过期"}
        if response.status_code == 403:
            return {"content": "", "sources": [], "error": "YOUCOM_API_KEY 权限不足"}
        if response.status_code != 200:
            return {"content": "", "sources": [], "error": f"You.com Research 失败 (Status {response.status_code})"}

        data = response.json()
        content = data.get("content", "")
        sources = []
        for source in data.get("sources", []):
            snippets = source.get("snippets", [])
            snippet = snippets[0] if isinstance(snippets, list) and snippets else ""
            sources.append({
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "snippet": snippet,
            })

        return {"content": content, "sources": sources}


_engine = YoucomResearchEngine()


@tool("youcom_research", parse_docstring=True)
def youcom_research(
    query: str,
    research_effort: Literal["lite", "standard", "deep", "exhaustive"] = "standard",
):
    """
    使用 You.com Research API 对给定主题进行深度研究，返回综述和引用来源。

    Args:
        query: 研究问题或主题（必填）
        research_effort: 研究深度，可选 lite（快速）、standard（标准）、deep（深入）、exhaustive（穷尽），默认 standard

    Returns:
        返回 markdown 格式的研究综述和引用来源列表
    """
    result = _engine.research(query, research_effort)
    if result.get("error"):
        return f"错误: {result['error']}"

    content = result.get("content", "")
    sources = result.get("sources", [])

    lines = []
    if content:
        lines.append(f"## 研究综述\n\n{content}")
    if sources:
        lines.append("\n## 引用来源\n")
        for i, s in enumerate(sources, 1):
            title = s.get("title", "未知来源")
            url = s.get("url", "")
            snippet = s.get("snippet", "")
            lines.append(f"[{i}] {title}\n   网址: {url}\n   摘要: {snippet}")

    return "\n".join(lines) if lines else "未返回有效结果"
