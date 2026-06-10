"""
Business API A — 用户数据服务
--------------------------------
生产对标：用户中心微服务（User Service）

验证规则：
  - 需要 audience=api-a 的 JWT
  - 需要 scope 包含 read:users 权限
  - 使用沙箱公钥离线验证签名

请求者不使用该地址，而是经过 Sidecar 透明代理（:9000/api-a/*）
"""

import asyncio
import logging

import httpx
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [API-A] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api-a")

try:
    import jwt as pyjwt
    from jwt import PyJWTError
except ImportError:
    raise

app = FastAPI(title="Business API A — User Service", version="1.0")

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
    """验证 audience=api-a 且 scope 包含 read:users 的 JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未提供认证令牌")

    token = authorization.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(
            token,
            _public_key_pem,
            algorithms=["RS256"],
            audience="api-a",
        )
        scope = payload.get("scope", "")
        if "read:users" not in scope:
            raise HTTPException(403, f"权限不足: 需要 read:users，当前 scope={scope}")
        log.info("令牌验证通过 | sub=%s | scope=%s", payload.get("sub"), scope)
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "令牌已过期")
    except PyJWTError as e:
        raise HTTPException(401, f"令牌无效: {e}")


@app.get("/protected-data")
async def protected_data(payload: dict = Depends(verify_token)):
    """返回受保护的用户数据"""
    log.info("返回用户数据 | client=%s", payload.get("client_id"))
    return {
        "service": "API-A (User Service)",
        "success": True,
        "user": {
            "user_id": "u_10086",
            "name": "张三",
            "email": "zhangsan@example.com",
            "level": "premium",
        },
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
    uvicorn.run(app, host="0.0.0.0", port=28100)
