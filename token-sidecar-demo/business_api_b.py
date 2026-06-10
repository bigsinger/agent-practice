"""
Business API B — 订单数据服务
--------------------------------
生产对标：订单中心微服务（Order Service）

验证规则：
  - 需要 audience=api-b 的 JWT
  - 需要 scope 包含 read:orders 权限
  - 使用沙箱公钥离线验证签名（与 API-A 使用同一把公钥，但 audience 不同）

这就是「多 API」场景：
  API-A 管用户    → 你的 JWT 必须有 audience=api-a
  API-B 管订单   → 你的 JWT 必须有 audience=api-b
  Sidecar 负责分别为不同请求换取不同的 JWT
"""

import asyncio
import logging

import httpx
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [API-B] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api-b")

try:
    import jwt as pyjwt
    from jwt import PyJWTError
except ImportError:
    raise

app = FastAPI(title="Business API B — Order Service", version="1.0")

_public_key_pem: str = ""
_kid: str = ""


async def fetch_public_key():
    global _public_key_pem, _kid
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:28001/public-key", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _kid = data["kid"]
        _public_key_pem = data["public_key"]
        log.info("公钥已就绪 | kid=%s", _kid)


@app.on_event("startup")
async def startup():
    for attempt in range(10):
        try:
            await fetch_public_key()
            return
        except Exception:
            log.warning("等待沙箱就绪 (attempt %d/10)...", attempt + 1)
            await asyncio.sleep(1)
    raise RuntimeError("沙箱未就绪")


async def verify_token(authorization: str = Header(None)):
    """验证 audience=api-b 且 scope 包含 read:orders 的 JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未提供认证令牌")

    token = authorization.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(
            token,
            _public_key_pem,
            algorithms=["RS256"],
            audience="api-b",
        )
        scope = payload.get("scope", "")
        if "read:orders" not in scope:
            raise HTTPException(403, f"权限不足: 需要 read:orders，当前 scope={scope}")
        log.info("令牌验证通过 | sub=%s | scope=%s", payload.get("sub"), scope)
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "令牌已过期")
    except PyJWTError as e:
        raise HTTPException(401, f"令牌无效: {e}")


@app.get("/protected-data")
async def protected_data(payload: dict = Depends(verify_token)):
    """返回受保护的订单数据"""
    log.info("返回订单数据 | client=%s", payload.get("client_id"))
    return {
        "service": "API-B (Order Service)",
        "success": True,
        "orders": [
            {"order_id": "ORD-20260601-001", "amount": 299.00, "status": "paid"},
            {"order_id": "ORD-20260601-002", "amount": 1599.50, "status": "shipped"},
            {"order_id": "ORD-20260602-003", "amount": 89.90, "status": "pending"},
        ],
        "total": 3,
        "token_info": {
            "audience": payload.get("aud"),
            "scope": payload.get("scope"),
            "issuer": payload.get("iss"),
            "expires_at": payload.get("exp"),
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "kid": _kid}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=28200)
