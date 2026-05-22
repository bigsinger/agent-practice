"""
Module 3 — MCP Security Gateway
================================
A security gateway that wraps MCP tools with:
  - Access logging (who called what, when)
  - Data masking / desensitization (phone, email, ID numbers)
  - Output safety detection (flag suspicious content)

Acts as a drop-in replacement for mcp_server.py — Hermes
connects to this instead for a "hardened" pipeline.
"""

import sys
import json
import re
import logging
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8001"
LOG_FILE = Path(__file__).parent / "gateway_access.log"

# ── Logging Setup ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("mcp-gateway")


# ── Security Functions ─────────────────────────────────────

def mask_sensitive(text: str) -> str:
    """
    脱敏处理：替换敏感字段为掩码格式。
    保持 JSON 结构完整，仅替换值内容。
    """
    # 手机号: 138****8001
    text = re.sub(r'(1[3-9]\d)\d{4}(\d{4})', r'\1****\2', text)
    # 身份证: 110101****1234
    text = re.sub(r'(\d{6})\d{8}(\d{4})', r'\1********\2', text)
    # 邮箱前缀: z****@internal.com
    text = re.sub(r'(\w)[\w.-]*@', r'\1****@', text)
    return text


def check_output_safety(text: str) -> list[str]:
    """
    输出安全检测：扫描返回内容中的敏感信息泄露风险。
    返回风险告警列表，空列表表示安全。
    """
    warnings = []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return warnings

    # 递归扫描所有字段
    def _scan(obj, path=""):
        nonlocal warnings
        if isinstance(obj, dict):
            for k, v in obj.items():
                child_path = f"{path}.{k}" if path else k
                if isinstance(v, str):
                    # 检测未脱敏的手机号
                    if re.match(r'^1[3-9]\d{9}$', v):
                        warnings.append(f"[泄露风险] 字段 '{child_path}' 包含未脱敏手机号: {v}")
                    # 检测未脱敏的完整邮箱
                    if re.match(r'^[\w.-]+@[\w.-]+\.\w+$', v):
                        warnings.append(f"[注意] 字段 '{child_path}' 包含邮箱: {v}")
                elif isinstance(v, (dict, list)):
                    _scan(v, child_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _scan(item, f"{path}[{i}]")

    _scan(data)
    return warnings


# ── MCP Server ─────────────────────────────────────────────

mcp = FastMCP(
    "demo-security-gateway",
    instructions="MCP 安全网关 — 包装 API 并添加日志、脱敏、安全检测",
)


def _api_get(path: str):
    resp = httpx.get(f"{API_BASE}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_user_info_safe(user_id: str) -> str:
    """【安全网关】查询用户信息（已脱敏处理，自动记录日志）"""
    logger.info(f"工具调用: get_user_info_safe(user_id='{user_id}')")

    raw = _api_get(f"/api/users/{user_id}")
    raw_str = json.dumps(raw, ensure_ascii=False)

    # 1. 脱敏处理
    masked = mask_sensitive(raw_str)

    # 2. 安全检测
    warnings = check_output_safety(masked)

    logger.info(f"响应大小: {len(masked)} 字符")
    if warnings:
        for w in warnings:
            logger.warning(f"安全告警: {w}")
    else:
        logger.info("安全检查: 通过")

    return masked


@mcp.tool()
def get_order_info_safe(order_id: str) -> str:
    """【安全网关】查询订单信息"""
    logger.info(f"工具调用: get_order_info_safe(order_id='{order_id}')")
    raw = _api_get(f"/api/orders/{order_id}")
    raw_str = json.dumps(raw, ensure_ascii=False)
    masked = mask_sensitive(raw_str)
    warnings = check_output_safety(masked)
    logger.info(f"响应大小: {len(masked)} 字符 | 告警数: {len(warnings)}")
    return masked


@mcp.tool()
def get_weather_safe(city: str) -> str:
    """【安全网关】查询天气（几乎无敏感信息，用于对比测试）"""
    logger.info(f"工具调用: get_weather_safe(city='{city}')")
    raw = _api_get(f"/api/weather/{city}")
    result = json.dumps(raw, ensure_ascii=False)
    logger.info(f"响应: {result}")
    return result


@mcp.tool()
def search_safe(keyword: str) -> str:
    """【安全网关】综合搜索"""
    logger.info(f"工具调用: search_safe(keyword='{keyword}')")
    raw = _api_get(f"/api/search?q={keyword}")
    raw_str = json.dumps(raw, ensure_ascii=False)
    masked = mask_sensitive(raw_str)
    warnings = check_output_safety(masked)
    return masked


@mcp.tool()
def get_user_orders_safe(user_id: str) -> str:
    """【安全网关】查询用户订单列表"""
    logger.info(f"工具调用: get_user_orders_safe(user_id='{user_id}')")
    raw = _api_get(f"/api/orders/by-user/{user_id}")
    raw_str = json.dumps(raw, ensure_ascii=False)
    masked = mask_sensitive(raw_str)
    warnings = check_output_safety(masked)
    return masked


if __name__ == "__main__":
    print("=" * 55)
    print("  MCP 安全网关 — demo-security-gateway")
    print(f"  日志文件: {LOG_FILE}")
    print(f"  后端 API: {API_BASE}")
    print("=" * 55)
    print()
    print(f"已注册的已脱敏工具:")
    print(f"  - get_user_info_safe(user_id)   — 用户查询 (脱敏)")
    print(f"  - get_order_info_safe(order_id) — 订单查询 (脱敏)")
    print(f"  - get_weather_safe(city)        — 天气查询 (明文)")
    print(f"  - search_safe(keyword)          — 综合搜索 (脱敏)")
    print(f"  - get_user_orders_safe(user_id) — 用户订单 (脱敏)")
    print()

    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
