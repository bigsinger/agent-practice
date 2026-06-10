"""
Sidecar 代理（透明拦截 + 多 API 令牌注入）
------------------------------------------
生产对标：Istio Envoy Sidecar / Linkerd-proxy

核心原理（生产环境）：
  Kubernetes 中，Pod 包含业务容器 + Sidecar 容器。
  iptables 规则将所有进出 Pod 的流量重定向到 Sidecar 的 15006 端口。
  业务进程完全不知道 Sidecar 存在。

本 Demo 的模拟方式：
  Sidecar 作为透明 API 网关监听 :9000。
  请求者认为 :9000/api-a/* 和 :9000/api-b/* 就是 API 地址，
  实际上 Sidecar 拦截了请求，完成了令牌置换后转发到后端。

拦截与置换逻辑（按请求路径自动路由）：
  ┌──────────┐    ┌─────────────────────────────────────────────┐    ┌───────────┐
  │ 请求者   │───▶│  Sidecar (:9000)                            │───▶│ API-A      │
  │          │    │  /api-a/... → 取 token-A → 注入 → 转发 :8100 │    │ (:8100)    │
  │ (零感知)  │    │  /api-b/... → 取 token-B → 注入 → 转发 :8200 │    │ API-B      │
  └──────────┘    └─────────────────────────────────────────────┘    │ (:8200)    │
                                       │                             └───────────┘
                                       ▼
                                 ┌──────────┐
                                 │ Sandbox   │
                                 │ (:8001)   │
                                 └──────────┘
"""

import time
import logging

import httpx
import uvicorn as uvicorn
from fastapi import FastAPI, Request, Response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIDE] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sidecar")

# ---------------------------------------------------------------------------
# 路由表（生产环境从控制平面动态发现，如 Istio Pilot / K8s Service）
# ---------------------------------------------------------------------------
ROUTES = {
    "/api-a": {
        "upstream": "http://localhost:28100",
        "audience": "api-a",
        "scope": "read:users",
        "service_name": "API-A (User Service)",
    },
    "/api-b": {
        "upstream": "http://localhost:28200",
        "audience": "api-b",
        "scope": "read:orders",
        "service_name": "API-B (Order Service)",
    },
}

SANDBOX_URL = "http://localhost:28001"

# ---------------------------------------------------------------------------
# Sidecar 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="Sidecar (Transparent Token Proxy)", version="2.0")

# 令牌缓存：{audience: {"token": str, "expires_at": float}}
_token_cache: dict[str, dict] = {}

GUARD_INTERVAL = 10  # 提前 10s 刷新


async def _fetch_token(audience: str, scope: str) -> tuple[str, int]:
    """从沙箱获取指定 audience 和 scope 的 JWT"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SANDBOX_URL}/token",
            json={
                "service": "sidecar",
                "audience": audience,
                "scope": scope,
                "ttl": 60,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"], data["expires_in"]


async def _ensure_token(audience: str, scope: str) -> str:
    """按 audience 缓存令牌，过期自动续期"""
    now = time.time()
    cached = _token_cache.get(audience)

    if cached and now < cached["expires_at"] - GUARD_INTERVAL:
        return cached["token"]

    log.info("令牌需要刷新 | audience=%s scope=%s", audience, scope)
    token, ttl = await _fetch_token(audience, scope)
    _token_cache[audience] = {"token": token, "expires_at": time.time() + ttl}
    log.info("令牌已缓存 | audience=%s | 有效期=%ds", audience, ttl)
    return token


async def _route_request(path: str, request: Request):
    """
    核心逻辑：根据请求路径匹配目标 API → 获取对应 JWT → 置换 → 转发
    """
    # ---- 1. 路由匹配 ----
    matched_prefix = None
    for prefix in sorted(ROUTES.keys(), key=len, reverse=True):
        if path.startswith(prefix):
            matched_prefix = prefix
            break

    if not matched_prefix:
        return Response(
            content=f'{{"error":"unknown route: {path}"}}',
            status_code=404,
            media_type="application/json",
        )

    route = ROUTES[matched_prefix]
    audience = route["audience"]
    scope = route["scope"]
    upstream = route["upstream"]

    # ---- 2. 获取目标 API 专用的 JWT ----
    token = await _ensure_token(audience, scope)

    # ---- 3. 构造转发请求 ----
    # 剥离匹配的前缀后再转发（请求者眼中的 /api-a/protected-data
    # 对应上游的 /api/protected-data）
    stripped_path = path[len(matched_prefix):] or "/"
    upstream_url = f"{upstream}{stripped_path}"
    body = await request.body()

    headers = dict(request.headers)
    # 移除所有可能被篡改的认证信息（生产环境可能来自客户端残余）
    headers.pop("authorization", None)
    headers.pop("x-dumb-key", None)
    headers.pop("host", None)
    headers["Host"] = upstream.split("://")[1]
    # 注入真实令牌
    headers["Authorization"] = f"Bearer {token}"
    headers.pop("content-length", None)
    headers.pop("transfer-encoding", None)

    log.info("拦截 → %s | 注入令牌 aud=%s | 转发 → %s%s",
             route["service_name"], audience, upstream, stripped_path)

    # ---- 4. 转发 ----
    async with httpx.AsyncClient() as client:
        try:
            upstream_resp = await client.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
                timeout=10,
            )
        except httpx.RequestError as e:
            log.error("上游不可达 | %s | %s", route["service_name"], e)
            return Response(
                content=f'{{"error":"upstream unreachable: {e}"}}',
                status_code=502,
                media_type="application/json",
            )

    # ---- 5. 返回 ----
    log.info("响应 | %s → %d", route["service_name"], upstream_resp.status_code)
    resp_headers = dict(upstream_resp.headers)
    for h in ("transfer-encoding", "connection", "keep-alive"):
        resp_headers.pop(h, None)

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------

@app.get("/api-a/{path:path}")
@app.get("/api-a")
async def proxy_api_a(request: Request, path: str = ""):
    return await _route_request(f"/api-a/{path}" if path else "/api-a", request)


@app.get("/api-b/{path:path}")
@app.get("/api-b")
async def proxy_api_b(request: Request, path: str = ""):
    return await _route_request(f"/api-b/{path}" if path else "/api-b", request)


# 健康检查
@app.get("/health")
async def health():
    token_info = {}
    for aud, cached in _token_cache.items():
        token_info[aud] = {
            "cached": time.time() < cached["expires_at"],
            "expires_in": max(0, int(cached["expires_at"] - time.time())),
        }
    return {
        "status": "ok",
        "routes": list(ROUTES.keys()),
        "tokens": token_info,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=29000)
