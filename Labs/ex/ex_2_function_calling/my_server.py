# my_server.py

import json

from mcp.server.fastmcp import FastMCP

from weather_tool import get_weather as weather_func
from fate_tool import calculate_fate_weight as fate_func


mcp = FastMCP("WeatherAndFateServer")


@mcp.tool()
def get_weather(location: str) -> str:
    """
    查詢指定城市天氣
    """
    return weather_func(location)


@mcp.tool()
def calculate_fate_weight(date_of_birth: str) -> str:
    """
    根據生日計算命重
    """
    result = fate_func(date_of_birth)

    return json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    )


if __name__ == "__main__":
    mcp.run()