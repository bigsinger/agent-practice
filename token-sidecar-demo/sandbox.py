"""
Sandbox / Token Vault v3 — 企业级密钥管理服务
================================================
生产对标：HashiCorp Vault / AWS KMS / Azure Key Vault

核心职责（真实 Vault 能力）：
  1. 持有 RSA 私钥（生产环境存 HSM）
  2. 身份认证（验证 Sidecar 的 Workload Identity）
  3. 签发限域 JWT（不同 audience + scope）
  4. 密钥轮换（新旧 kid 共存，平滑过渡）
  5. 令牌吊销（JTI 黑名单即时失效）
  6. 审计日志（所有操作全记录）

Sidecar → 沙箱认证流程（模拟 K8s Workload Identity）：
  Sidecar                              Sandbox
    │── POST /vault/auth ─────────────▶│
    │   {workload_id: "..."}           │  ← 模拟 K8s Service Account
    │◀── {vault_token: "..."} ─────────│  ← 限域沙箱会话令牌
    │                                   │
    │── POST /vault/token ────────────▶│
    │   Authorization: Bearer <vault..> │
    │   {audience, scope, user}         │
    │◀── {access_token} ───────────────│
"""

import asyncio
import json
import logging
import time
import uuid

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [VAULT] %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger("vault")

try:
    import jwt as pyjwt
    from jwt import PyJWTError
except ImportError:
    raise

app = FastAPI(title="Sandbox / Token Vault", version="3.0")

# ---------------------------------------------------------------------------
# 密钥环（支持多 kid 共存，用于轮换过渡）
# ---------------------------------------------------------------------------
_key_ring: list[dict] = []       # [{kid, private_key, public_key_pem, created_at, active}]
PRIMARY_KEY_TTL = 300            # 每 5 分钟轮换一次（演示用）
VAULT_SECRET = "vault-internal-secret-2026"

# ---------------------------------------------------------------------------
# 令牌吊销与审计
# ---------------------------------------------------------------------------
_revoked_tokens: set = set()     # JTI 黑名单
_audit_log: list = []            # 审计日志

# ---------------------------------------------------------------------------
# 可信任的 Workload ID（生产环境通过配置或 K8s Webhook 动态注册）
# ---------------------------------------------------------------------------
_TRUSTED_WORKLOADS = {"sidecar-prod-01", "sidecar-prod-02"}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AuthRequest(BaseModel):
    workload_id: str

class TokenRequest(BaseModel):
    audience: str
    scope: str = "read"
    ttl: int = 60
    user_info: dict = {}         # Sidecar 传过来的用户信息

class RevokeRequest(BaseModel):
    jti: str

class RotateResponse(BaseModel):
    new_kid: str
    active_keys: int
    message: str


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _init_key_ring():
    """初始化密钥环——生成主密钥"""
    global _key_ring
    _key_ring = [_generate_key(active=True)]
    log.info("密钥环初始化 | kid=%s | 密钥数=1", _key_ring[0]["kid"])

def _generate_key(active: bool = True) -> dict:
    """生成 RSA-2048 密钥对"""
    pk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = pk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    kid = f"key-{uuid.uuid4().hex[:8]}"
    return dict(kid=kid, private_key=pk, public_key_pem=pub_pem,
                created_at=int(time.time()), active=active)

def _find_key(kid: str):
    """按 kid 查找密钥（包括已轮换的非活跃密钥，用于验证存量令牌）"""
    for k in _key_ring:
        if k["kid"] == kid:
            return k
    return None

def _active_key() -> dict:
    """获取当前活跃的签发密钥"""
    for k in _key_ring:
        if k["active"]:
            return k
    return _key_ring[-1]  # fallback

def _audit(event: str, detail: dict):
    """写入审计日志"""
    entry = dict(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        event=event,
        detail=detail,
    )
    _audit_log.append(entry)
    log.info("AUDIT | %s | %s", event, json.dumps(detail, ensure_ascii=False))

def _issue_vault_token(workload_id: str) -> str:
    """给 Sidecar 签发限域 Vault 会话令牌"""
    now = int(time.time())
    payload = dict(
        iss="vault.starcloud.com",
        sub=workload_id,
        scope="token:issue token:revoke keys:read audit:read",
        iat=now,
        exp=now + 300,       # 5 分钟
        jti=uuid.uuid4().hex,
    )
    return pyjwt.encode(payload, VAULT_SECRET, algorithm="HS256")

def verify_vault_token(authorization: str = Header(None)) -> dict:
    """验证 Sidecar 的 Vault 令牌"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未提供 Vault 认证令牌")
    token = authorization.split(" ", 1)[1]
    try:
        p = pyjwt.decode(token, VAULT_SECRET, algorithms=["HS256"])
        if p.get("jti") in _revoked_tokens:
            raise HTTPException(401, "Vault 令牌已吊销")
        return p
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Vault 令牌已过期")
    except PyJWTError:
        raise HTTPException(401, "无效 Vault 令牌")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    _init_key_ring()
    _audit("vault.startup", {"kid": _key_ring[0]["kid"]})


@app.post("/vault/auth", response_model=dict)
async def vault_auth(req: AuthRequest):
    """
    Sidecar 使用 Workload Identity 向 Vault 认证。
    
    ⚡ 生产环境：K8s Service Account JWT / AWS Instance Role
    本演示：预配置的可信任 workload_id 列表
    """
    if req.workload_id not in _TRUSTED_WORKLOADS:
        _audit("auth.failed", {"workload_id": req.workload_id, "reason": "not_trusted"})
        raise HTTPException(403, f"不可信任的 Workload: {req.workload_id}")

    vault_token = _issue_vault_token(req.workload_id)
    _audit("auth.success", {"workload_id": req.workload_id})
    return dict(vault_token=vault_token, workload_id=req.workload_id, ttl=300)


@app.post("/vault/token")
async def issue_service_token(req: TokenRequest, p: dict = Depends(verify_vault_token)):
    """
    签发服务间调用的 JWT 令牌。
    
    验证逻辑：
      - 必须持有有效的 Vault 会话令牌（来自 /vault/auth）
      - 检查 JTI 是否被吊销
      - 使用当前活跃的签发密钥
    """
    active = _active_key()
    now = int(time.time())

    payload = dict(
        iss="vault.starcloud.com",
        sub=p.get("sub", "sidecar"),
        aud=req.audience,
        scope=req.scope,
        iat=now,
        exp=now + req.ttl,
        jti=uuid.uuid4().hex,
        client_id=p.get("sub"),
        user_info=req.user_info,   # 携带用户身份信息
    )

    token = pyjwt.encode(payload, active["private_key"], algorithm="RS256",
                         headers=dict(kid=active["kid"]))

    _audit("token.issue", {
        "audience": req.audience,
        "scope": req.scope,
        "ttl": req.ttl,
        "jti": payload["jti"],
        "kid": active["kid"],
        "client": p.get("sub"),
        "user": req.user_info.get("user_id", "unknown"),
    })

    return dict(access_token=token, token_type="Bearer",
                expires_in=req.ttl, kid=active["kid"], jti=payload["jti"])


@app.post("/vault/token/revoke")
async def revoke_token(req: RevokeRequest, p: dict = Depends(verify_vault_token)):
    """吊销指定 JTI 的令牌"""
    _revoked_tokens.add(req.jti)
    _audit("token.revoke", {
        "jti": req.jti,
        "by": p.get("sub"),
    })
    return dict(success=True, jti=req.jti)


@app.post("/vault/keys/rotate")
async def rotate_keys(p: dict = Depends(verify_vault_token)):
    """
    轮换签名密钥。
    
    策略：
      - 新密钥成为活跃密钥（active=True）
      - 旧密钥保留在密钥环中（active=False），用于验证存量令牌
      - 旧密钥数量超过 3 个时，删除最旧的（确保存量令牌可验证过渡期）
    """
    new_key = _generate_key(active=True)
    # 旧密钥降级
    for k in _key_ring:
        k["active"] = False
    _key_ring.append(new_key)
    # 保留最多 4 个密钥（1 活跃 + 3 备用）
    while len(_key_ring) > 4:
        removed = _key_ring.pop(0)
        _audit("key.evicted", {"kid": removed["kid"]})

    _audit("key.rotate", {"new_kid": new_key["kid"], "total_keys": len(_key_ring)})
    return RotateResponse(new_kid=new_key["kid"], active_keys=len(_key_ring),
                          message=f"密钥轮换完成 | 活跃: {new_key['kid']} | 备用: {len(_key_ring)-1}")


@app.get("/vault/keys")
async def list_keys(p: dict = Depends(verify_vault_token)):
    """列出所有密钥（不含私钥）"""
    result = []
    for k in _key_ring:
        result.append(dict(
            kid=k["kid"], created_at=k["created_at"],
            active=k["active"], public_key=k["public_key_pem"][:80]+"...",
        ))
    return dict(keys=result, total=len(result))


@app.get("/vault/audit")
async def get_audit_log(p: dict = Depends(verify_vault_token)):
    """获取审计日志"""
    return dict(logs=_audit_log, total=len(_audit_log))


@app.get("/public-key")
async def get_public_key():
    """返回当前活跃的公钥（供业务 API 验证）"""
    active = _active_key()
    return dict(kid=active["kid"], public_key=active["public_key_pem"])


@app.get("/health")
async def health():
    active = _active_key()
    return dict(status="ok", kid=active["kid"], keys=len(_key_ring),
                revoked=len(_revoked_tokens), audit_count=len(_audit_log))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=28001)
