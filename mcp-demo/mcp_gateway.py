"""
Module 3 — MCP Security Gateway (v2)
======================================
A security gateway that wraps MCP tools with:
  - Token-based authentication (only valid tokens pass through)
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

# ── Token Authentication ─────────────────────────────────────
# Tokens act as simple shared secrets. In production, replace with
# JWT / OAuth / MCP session context.
VALID_TOKENS = {
    "demo-token-2026": "standard",
    "admin-token-2026": "admin",
}

TOKEN_DISPLAY = {
    "demo-token-2026": "Demo Token（标准权限）",
    "admin-token-2026": "Admin Token（管理员权限）",
}

TOKEN_HINT = (
    "Token 认证：所有工具需传入 token 参数。\n"
    f"  有效 Token: {', '.join(VALID_TOKENS.keys())}\n"
    "  示例: get_user_info_safe(token='demo-token-2026', user_id='u001')"
)


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


def verify_token(token: str) -> str | None:
    """
    验证 token 是否有效。
    返回 None 表示无效；返回 token 级别名称（如 'standard', 'admin'）表示有效。
    """
    level = VALID_TOKENS.get(token)
    if level is None:
        logger.warning(f"[认证失败] 无效 token (前缀: {token[:6]}...)")
        return None
    role = TOKEN_DISPLAY.get(token, token)
    logger.info(f"[认证成功] token={role}, 级别={level}")
    return level


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
    instructions="MCP 安全网关 — 认证 + 日志 + 脱敏 + 安全检测\n\n" + TOKEN_HINT,
)


def _api_get(path: str):
    resp = httpx.get(f"{API_BASE}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _auth_err(token: str) -> str:
    """返回认证失败的 JSON 错误。"""
    err = {
        "error": "unauthorized",
        "message": "无效的 token，请使用有效 Token",
        "hint": list(VALID_TOKENS.keys()),
    }
    return json.dumps(err, ensure_ascii=False)


def _process_and_return(raw, tool_name: str) -> str:
    """对原始响应执行脱敏+检测+日志，返回处理后的字符串。"""
    raw_str = json.dumps(raw, ensure_ascii=False)
    masked = mask_sensitive(raw_str)
    warnings = check_output_safety(masked)

    logger.info(f"响应大小: {len(masked)} 字符")
    if warnings:
        for w in warnings:
            logger.warning(f"安全告警: {w}")
    else:
        logger.info("安全检查: 通过")

    return masked


@mcp.tool()
def get_user_info_safe(token: str, user_id: str) -> str:
    """【安全网关】查询用户信息（需 Token 认证，已脱敏处理）"""
    logger.info(f"工具调用: get_user_info_safe(user_id='{user_id}')")

    if verify_token(token) is None:
        return _auth_err(token)

    raw = _api_get(f"/api/users/{user_id}")
    return _process_and_return(raw, "get_user_info_safe")


@mcp.tool()
def get_order_info_safe(token: str, order_id: str) -> str:
    """【安全网关】查询订单信息（需 Token 认证）"""
    logger.info(f"工具调用: get_order_info_safe(order_id='{order_id}')")

    if verify_token(token) is None:
        return _auth_err(token)

    raw = _api_get(f"/api/orders/{order_id}")
    return _process_and_return(raw, "get_order_info_safe")


@mcp.tool()
def get_weather_safe(token: str, city: str) -> str:
    """【安全网关】查询天气（需 Token 认证，几乎无敏感信息）"""
    logger.info(f"工具调用: get_weather_safe(city='{city}')")

    if verify_token(token) is None:
        return _auth_err(token)

    raw = _api_get(f"/api/weather/{city}")
    result = json.dumps(raw, ensure_ascii=False)
    logger.info(f"响应: {result}")
    return result


@mcp.tool()
def search_safe(token: str, keyword: str) -> str:
    """【安全网关】综合搜索（需 Token 认证）"""
    logger.info(f"工具调用: search_safe(keyword='{keyword}')")

    if verify_token(token) is None:
        return _auth_err(token)

    raw = _api_get(f"/api/search?q={keyword}")
    return _process_and_return(raw, "search_safe")


@mcp.tool()
def get_user_orders_safe(token: str, user_id: str) -> str:
    """【安全网关】查询用户订单列表（需 Token 认证）"""
    logger.info(f"工具调用: get_user_orders_safe(user_id='{user_id}')")

    if verify_token(token) is None:
        return _auth_err(token)

    raw = _api_get(f"/api/orders/by-user/{user_id}")
    return _process_and_return(raw, "get_user_orders_safe")


if __name__ == "__main__":
    print("=" * 60)
    print("  MCP 安全网关 v2 — demo-security-gateway")
    print(f"  日志文件: {LOG_FILE}")
    print(f"  后端 API: {API_BASE}")
    print("=" * 60)
    print()
    print("  🔐 Token 认证已启用!")
    print(f"  有效 Token: {', '.join(VALID_TOKENS.keys())}")
    print()
    print("  已注册的已脱敏工具 (需 token 参数):")
    print(f"  - get_user_info_safe(token, user_id)   — 用户查询")
    print(f"  - get_order_info_safe(token, order_id) — 订单查询")
    print(f"  - get_weather_safe(token, city)        — 天气查询")
    print(f"  - search_safe(token, keyword)          — 综合搜索")
    print(f"  - get_user_orders_safe(token, user_id) — 用户订单")
    print()

    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
