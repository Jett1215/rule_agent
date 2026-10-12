"""Validate and format responses from the AMap forecast service."""

import logging

import requests


def query_weather(location, config, weather_prompt, message_prompt):
    if not config or not config.get("api_key"):
        return "天气查询不可用：未配置高德天气 API Key，请联系管理员配置。"
    if not config.get("endpoint"):
        return "天气查询不可用：未配置天气接口地址，请联系管理员配置。"
    if not location or not location.strip():
        return "请提供需要查询天气的城市名称。"

    try:
        response = requests.get(
            config["endpoint"],
            params={"key": config["api_key"], "city": location.strip(), "extensions": "all"},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()
    except requests.Timeout:
        return "天气查询超时，请稍后重试。"
    except requests.RequestException:
        # Request exception strings can contain the API key in the URL.
        logging.warning("Weather service request failed")
        return "天气服务请求失败，请稍后重试或联系管理员检查接口连接。"
    except ValueError:
        return "天气服务返回了无效的数据，请稍后重试。"

    if not isinstance(result, dict):
        return "天气服务返回了无效的数据，请稍后重试。"
    if str(result.get("status")) != "1":
        code = str(result.get("infocode", ""))
        if code == "10001" or result.get("info") == "INVALID_USER_KEY":
            return "天气查询不可用：高德天气 API Key 无效（INVALID_USER_KEY，10001），请联系管理员更换有效的 Web 服务 Key。"
        return "天气服务未能完成查询，请联系管理员检查高德 Key 的权限、配额及接口配置。"

    forecasts = result.get("forecasts")
    if not isinstance(forecasts, list) or not forecasts or not isinstance(forecasts[0], dict):
        return "未查询到该城市的天气预报，请确认城市名称或使用城市行政区划编码。"
    forecast = forecasts[0]
    casts = forecast.get("casts")
    fields = ("date", "daytemp", "nighttemp", "dayweather", "nightweather")
    if not isinstance(casts, list) or not casts:
        return "该城市暂无可用的天气预报，请稍后重试。"
    if any(not isinstance(item, dict) or any(item.get(field) is None for field in fields) for item in casts):
        return "天气服务返回的预报数据不完整，请稍后重试。"
    messages = [message_prompt.format(*(item[field] for field in fields)) for item in casts]
    return weather_prompt.format(forecast.get("city") or location, messages[0], "\n".join(messages[1:]) or "暂无更多预报")
