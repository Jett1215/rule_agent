import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agentchat.settings import init_app_settings


class WorkspaceMcpArgumentsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_app_settings()

    async def test_generated_mcp_event_includes_fixed_query_and_redacts_secrets(self):
        from agentchat.database.dao.register_mcp import RegisterMcpDao
        from agentchat.services.workspace.simple_agent import WorkSpaceSimpleAgent

        agent = WorkSpaceSimpleAgent.__new__(WorkSpaceSimpleAgent)
        agent.mcp_configs = [SimpleNamespace(
            server_name="实时天气查询",
            url="http://127.0.0.1:7860/mcp/63742310-275b-4c7f-87d0-2ff107948ca0",
        )]
        tool = SimpleNamespace(api_info={
            "base_url": "https://api.open-meteo.com",
            "path": "/v1/forecast?current=temperature_2m",
        })

        with patch.object(RegisterMcpDao, "get_tool_by_name", new_callable=AsyncMock, return_value=tool):
            arguments = {"latitude": 30.27, "longitude": 120.2, "api_key": "private"}
            visible = await agent._get_visible_mcp_arguments("实时天气查询", "get_v1_forecast", arguments)

        self.assertEqual(visible, {
            "latitude": 30.27,
            "longitude": 120.2,
            "api_key": "***",
            "current": "temperature_2m",
        })
        self.assertEqual(arguments["api_key"], "private")


if __name__ == "__main__":
    unittest.main()
