"""
Sandbox（沙箱 / Token Vault）
--------------------------------
生产对标：HashiCorp Vault / AWS KMS

职责：
  - 持有 RSA 密钥对
  - 签发不同 scope 的 JWT（API-A 和 API-B 使用不同的 audience）
  - 提供公钥供业务 API 离线验证

变更说明 v2：
  - `/token` 支持 audience 参数，可签发不同目标服务的令牌
  - 新增 `/token/api-a` 和 `/token/api-b` 便捷端点
"""

import time
import uuid
import logging

import uvicorn
from fastapi import FastAPI
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SAND] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sandbox")

try:
    import jwt as pyjwt
except ImportError:
    log.error("请安装依赖: pip install PyJWT cryptography")
    raise

app = FastAPI(title="Sandbox / Token Vault", version="2.0")

_private_key: rsa.RSAPrivateKey | None = None
_public_key_pem: str = ""
_kid: str = ""


class TokenRequest(BaseModel):
    """令牌签发请求"""
    service: str          # 请求方身份（如 "sidecar"）
    audience: str         # 目标服务（如 "api-a" / "api-b"）
    scope: str = "read"   # 权限范围
    ttl: int = 60         # 有效期（秒）


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    kid: str


@app.on_event("startup")
async def init_keys():
    global _private_key, _public_key_pem, _kid
    log.info("正在生成 RSA-2048 密钥对...")
    _private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    _public_key_pem = _private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    _kid = f"key-{uuid.uuid4().hex[:8]}"
    log.info("密钥对就绪 | kid=%s", _kid)


def _issue_token(service: str, audience: str, scope: str, ttl: int) -> str:
    """签发 RS256 JWT"""
    now = int(time.time())
    payload = {
        "iss": "sandbox-vault",
        "sub": service,
        "aud": audience,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
        "client_id": "sidecar-prod-01",
        "scope": scope,
    }
    token = pyjwt.encode(
        payload,
        _private_key,
        algorithm="RS256",
        headers={"kid": _kid},
    )
    log.info("签发令牌 | aud=%s | scope=%s | exp=%ds | jti=%s",
             audience, scope, ttl, payload["jti"])
    return token


@app.post("/token")
async def issue_token(req: TokenRequest):
    """通用签发接口"""
    token = _issue_token(req.service, req.audience, req.scope, req.ttl)
    return TokenResponse(access_token=token, expires_in=req.ttl, kid=_kid)


@app.post("/token/api-a")
async def token_for_api_a():
    """签发 API-A 专用令牌（用户数据级别）"""
    token = _issue_token("sidecar", "api-a", "read:users", 60)
    return TokenResponse(access_token=token, expires_in=60, kid=_kid)


@app.post("/token/api-b")
async def token_for_api_b():
    """签发 API-B 专用令牌（订单数据级别）"""
    token = _issue_token("sidecar", "api-b", "read:orders", 60)
    return TokenResponse(access_token=token, expires_in=60, kid=_kid)


@app.get("/public-key")
async def get_public_key():
    return {"kid": _kid, "public_key": _public_key_pem}


@app.get("/health")
async def health():
    return {"status": "ok", "kid": _kid}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=28001)
