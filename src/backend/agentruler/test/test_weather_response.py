import unittest
from unittest.mock import patch

import requests

from agentruler.utils.weather import query_weather


class WeatherResponseTests(unittest.TestCase):
    def query(self):
        return query_weather("上海", {"api_key": "test-key", "endpoint": "https://example.test"}, "{}\n{}\n{}", "{} {} {} {} {}")

    @patch("agentruler.utils.weather.requests.get")
    def test_invalid_key(self, get):
        get.return_value.json.return_value = {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        self.assertIn("API Key 无效", self.query())

    @patch("agentruler.utils.weather.requests.get")
    def test_missing_forecasts(self, get):
        for forecasts in (None, [], {}, [None]):
            with self.subTest(forecasts=forecasts):
                get.return_value.json.return_value = {"status": "1", "forecasts": forecasts}
                self.assertIn("未查询到", self.query())

    @patch("agentruler.utils.weather.requests.get")
    def test_missing_casts(self, get):
        for casts in (None, [], [None], [{}]):
            with self.subTest(casts=casts):
                get.return_value.json.return_value = {"status": "1", "forecasts": [{"casts": casts}]}
                self.assertNotIn("NoneType", self.query())
                self.assertIn("请稍后重试", self.query())

    @patch("agentruler.utils.weather.requests.get")
    def test_success(self, get):
        cast = dict(date="2026-09-28", daytemp="28", nighttemp="22", dayweather="晴", nightweather="多云")
        get.return_value.json.return_value = {"status": "1", "forecasts": [{"city": "上海市", "casts": [cast, cast]}]}
        message = self.query()
        self.assertIn("上海市", message)
        self.assertEqual(message.count("2026-09-28"), 2)
        self.assertNotIn("['", message)

    @patch("agentruler.utils.weather.requests.get")
    def test_request_errors(self, get):
        for error, expected in ((requests.Timeout(), "超时"), (requests.ConnectionError("secret-key"), "请求失败")):
            get.side_effect = error
            message = self.query()
            self.assertIn(expected, message)
            self.assertNotIn("secret-key", message)

    @patch("agentruler.utils.weather.requests.get")
    def test_http_and_json_errors(self, get):
        get.return_value.raise_for_status.side_effect = requests.HTTPError("secret-key")
        self.assertIn("请求失败", self.query())
        get.return_value.raise_for_status.side_effect = None
        get.return_value.json.side_effect = ValueError()
        self.assertIn("无效的数据", self.query())
        get.return_value.json.side_effect = None
        get.return_value.json.return_value = None
        self.assertIn("无效的数据", self.query())

    @patch("agentruler.utils.weather.requests.get")
    def test_missing_config(self, get):
        self.assertIn("未配置", query_weather("上海", None, "", ""))
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
