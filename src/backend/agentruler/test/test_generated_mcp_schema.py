import json
import unittest
from types import SimpleNamespace

from agentruler.mcp_proxy.schema_converter import tool_to_mcp_schema


class GeneratedMcpSchemaTests(unittest.TestCase):
    def test_generated_query_parameters_have_valid_tool_schema(self):
        tool = SimpleNamespace(
            name="get_v1_forecast",
            description="查询当前气温",
            parameters=json.dumps({
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "纬度",
                        "x_position": "query",
                        "default": None,
                        "items": None,
                    },
                    "longitude": {
                        "type": "number",
                        "x_position": "query",
                        "items": None,
                    },
                },
                "required": ["latitude", "longitude"],
                "additionalProperties": False,
            }),
        )

        schema = tool_to_mcp_schema(tool)["inputSchema"]

        self.assertEqual(schema["required"], ["latitude", "longitude"])
        self.assertIs(schema["additionalProperties"], False)
        for property_schema in schema["properties"].values():
            self.assertNotIn("items", property_schema)
            self.assertNotIn("x_position", property_schema)

    def test_nullable_top_level_fields_are_omitted(self):
        tool = SimpleNamespace(
            name="legacy_tool",
            description="",
            parameters=json.dumps({
                "type": "object",
                "properties": {},
                "required": None,
                "additionalProperties": None,
            }),
        )

        schema = tool_to_mcp_schema(tool)["inputSchema"]

        self.assertNotIn("required", schema)
        self.assertNotIn("additionalProperties", schema)


if __name__ == "__main__":
    unittest.main()
