"""
Module 2 — MCP Wrapper Server
==============================
Wraps the REST API (api_service) into MCP Tool format.
Runs on stdio transport — Hermes Agent connects to it directly.

Usage:  python mcp_server.py          # starts in stdio mode
Or  :  python mcp_server.py --sse     # starts in SSE mode for debugging
"""

import sys
import json
import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8001"

# Create MCP server instance
mcp = FastMCP(
    "demo-api-wrapper",
    instructions="将模拟 REST API 包装为 MCP 工具，演示 MCP 完整链路",
)


def _api_get(path: str):
    """Helper: call the underlying REST API."""
    resp = httpx.get(f"{API_BASE}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── MCP Tools ──────────────────────────────────────────────

@mcp.tool()
def get_user_info(user_id: str) -> str:
    """根据用户ID查询用户详细信息（姓名、电话、邮箱、角色、部门）"""
    data = _api_get(f"/api/users/{user_id}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def get_order_info(order_id: str) -> str:
    """根据订单ID查询订单详细信息（产品、金额、状态、日期）"""
    data = _api_get(f"/api/orders/{order_id}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的天气情况（温度、湿度、天气状况）"""
    data = _api_get(f"/api/weather/{city}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def search(keyword: str) -> str:
    """综合搜索：按关键词搜索用户、订单等信息"""
    data = _api_get(f"/api/search?q={keyword}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def get_user_orders(user_id: str) -> str:
    """查询指定用户的所有订单列表"""
    data = _api_get(f"/api/orders/by-user/{user_id}")
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Default: stdio transport (for Hermes Agent integration)
    # Pass --sse for browser-based debugging
    if "--sse" in sys.argv:
        print("[MCP Server] 启动 SSE 模式，用于浏览器调试...")
        mcp.run(transport="sse")
    else:
        print("[MCP Server] 启动 stdio 模式，等待 Hermes Agent 连接...")
        print(f"[MCP Server] 后端 API: {API_BASE}")
        print(f"[MCP Server] 已注册工具: get_user_info, get_order_info, get_weather, search, get_user_orders")
        mcp.run(transport="stdio")
