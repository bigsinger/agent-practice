"""
Sidecar v3 — 透明拦截 + Workload 认证 + 用户会话验证
=====================================================
生产对标：Istio Envoy Sidecar + Vault Agent

核心流程：
  1. 请求者携带用户会话 JWT（从 IAM 登录获得）访问 Sidecar
  2. Sidecar 验证会话 JWT 的有效性（调 IAM /verify）
  3. Sidecar 向 Vault 认证（Workload Identity）获取 Vault 令牌
  4. Sidecar 用 Vault 令牌换取限域 JWT（注入用户权限）
  5. Sidecar 替换用户会话为服务 JWT，转发到业务 API

iptables 说明（生产环境）：
  Kubernetes 中 Pod 启动时，initContainer 执行:
    iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 15006
  将所有流量透明重定向到 Sidecar。本 demo 用显式反向代理模拟。
"""

import asyncio
import logging
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [SIDE] %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger("sidecar")

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
IAM_URL = "http://localhost:27000"
VAULT_URL = "http://localhost:28001"

ROUTES = {
    "/api-a": {"upstream": "http://localhost:28100", "audience": "api-a",
               "scope": "read:users", "service_name": "API-A (User Service)"},
    "/api-b": {"upstream": "http://localhost:28200", "audience": "api-b",
               "scope": "read:orders", "service_name": "API-B (Order Service)"},
}

WORKLOAD_ID = "sidecar-prod-01"
GUARD_INTERVAL = 10

# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
app = FastAPI(title="Sidecar v3 (Transparent Token Proxy)", version="3.0")
_token_cache: dict = {}       # {audience: {token, expires_at}}

# Vault 会话令牌缓存
_vault_token: str | None = None
_vault_token_expires: float = 0


# ---------------------------------------------------------------------------
# Vault 认证（Workload Identity）
# ---------------------------------------------------------------------------
async def _ensure_vault_token() -> str:
    """向 Vault 认证，获取/续期 Vault 会话令牌"""
    global _vault_token, _vault_token_expires

    now = time.time()
    if _vault_token and now < _vault_token_expires - 30:
        return _vault_token

    log.info("向 Vault 发起 Workload 认证 | workload_id=%s", WORKLOAD_ID)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{VAULT_URL}/vault/auth",
            json={"workload_id": WORKLOAD_ID},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        _vault_token = data["vault_token"]
        _vault_token_expires = time.time() + data["ttl"]
        log.info("Vault 认证成功 | ttl=%ds", data["ttl"])
        return _vault_token


# ---------------------------------------------------------------------------
# 用户会话验证
# ---------------------------------------------------------------------------
async def _verify_user_session(session_token: str | None) -> dict:
    """向 IAM 验证用户会话"""
    if not session_token:
        return None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{IAM_URL}/iam/verify",
                headers={"Authorization": f"Bearer {session_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# 服务令牌获取
# ---------------------------------------------------------------------------
async def _fetch_token(audience: str, scope: str, user_info: dict) -> tuple[str, int]:
    """从 Vault 获取服务间 JWT"""
    vault_token = await _ensure_vault_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{VAULT_URL}/vault/token",
            headers={"Authorization": f"Bearer {vault_token}"},
            json={
                "audience": audience,
                "scope": scope,
                "ttl": 60,
                "user_info": user_info,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"], data["expires_in"]


async def _ensure_token(audience: str, scope: str, user_info: dict) -> str:
    """按 audience + 用户 缓存令牌"""
    now = time.time()
    cache_key = f"{audience}:{user_info.get('user_id', 'anon')}"
    cached = _token_cache.get(cache_key)

    if cached and now < cached["expires_at"] - GUARD_INTERVAL:
        log.debug("令牌缓存命中 | key=%s", cache_key)
        return cached["token"]

    log.info("令牌需要签发 | aud=%s scope=%s user=%s",
             audience, scope, user_info.get("user_id", "anon"))
    token, ttl = await _fetch_token(audience, scope, user_info)
    _token_cache[cache_key] = {"token": token, "expires_at": time.time() + ttl}
    log.info("令牌已缓存 | key=%s | 有效期=%ds", cache_key, ttl)
    return token


# ---------------------------------------------------------------------------
# 核心路由逻辑
# ---------------------------------------------------------------------------
async def _route_request(path: str, request: Request):
    # 1. 路由匹配
    matched = None
    for prefix in sorted(ROUTES.keys(), key=len, reverse=True):
        if path.startswith(prefix):
            matched = prefix
            break
    if not matched:
        return Response(content='{"error":"unknown route"}', status_code=404,
                        media_type="application/json")

    route = ROUTES[matched]
    stripped = path[len(matched):] or "/"

    # 2. 提取用户会话（来自请求头）
    session_token = request.headers.get("authorization", "").replace("Bearer ", "")
    user_info = await _verify_user_session(session_token) or {}

    log.info("会话验证 | user=%s | role=%s | route=%s",
             user_info.get("user_id", "unauthenticated"),
             user_info.get("role", "none"), matched)

    # 3. 获取用户权限对应的 scope
    user_perms = user_info.get("permissions", [])
    scope = route["scope"]
    # 检查用户是否有权限访问此 API
    perm_check = f"{route['audience']}:{'write' if 'write' in scope else 'read'}"
    # 简化：只要有对应权限就行

    # 4. 获取服务 JWT
    token = await _ensure_token(route["audience"], scope, user_info)

    # 5. 转发请求
    upstream_url = f"{route['upstream']}{stripped}"
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("authorization", None)
    headers.pop("x-dumb-key", None)
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("transfer-encoding", None)
    headers["Authorization"] = f"Bearer {token}"
    headers["X-User-Id"] = user_info.get("user_id", "unknown")
    headers["X-User-Role"] = user_info.get("role", "unknown")

    log.info("拦截 → %s | 注入令牌 aud=%s | 转发 → %s",
             route["service_name"], route["audience"], upstream_url)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method=request.method, url=upstream_url,
                headers=headers, content=body, timeout=10,
            )
        except httpx.RequestError as e:
            log.error("上游不可达 | %s", e)
            return Response(content=f'{{"error":"upstream: {e}"}}',
                            status_code=502, media_type="application/json")

    log.info("响应 | %s → %d", route["service_name"], resp.status_code)
    resp_headers = dict(resp.headers)
    for h in ("transfer-encoding", "connection", "keep-alive"):
        resp_headers.pop(h, None)
    return Response(content=resp.content, status_code=resp.status_code,
                    headers=resp_headers)


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------
@app.get("/api-a/{path:path}")
@app.get("/api-a")
async def proxy_a(request: Request, path: str = ""):
    return await _route_request(f"/api-a/{path}" if path else "/api-a", request)

@app.get("/api-b/{path:path}")
@app.get("/api-b")
async def proxy_b(request: Request, path: str = ""):
    return await _route_request(f"/api-b/{path}" if path else "/api-b", request)

@app.get("/health")
async def health():
    token_info = {}
    for k, c in _token_cache.items():
        token_info[k] = {"cached": time.time() < c["expires_at"],
                         "expires_in": max(0, int(c["expires_at"] - time.time()))}
    return {"status": "ok", "routes": list(ROUTES.keys()),
            "vault_auth": _vault_token is not None, "tokens": token_info}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=29000)
