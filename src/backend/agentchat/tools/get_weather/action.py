from langchain.tools import tool

from agentchat.settings import app_settings
from agentchat.utils.weather import query_weather
from agentchat.prompts.tool import WEATHER_PROMPT, MESSAGE_PROMPT


@tool(parse_docstring=True)
def get_weather(city: str):
    """
    查询用户提供城市的天气情况。

    Args:
        city (str): 用户提供的城市名称。

    Returns:
        str: 城市的天气信息。
    """
    return _get_weather(city)

def _get_weather(location: str):
    """帮助用户想要查询的天气"""
    config = getattr(app_settings.tools, "weather", None)
    return query_weather(location, config, WEATHER_PROMPT, MESSAGE_PROMPT)
