"""
IAM 身份与访问管理系统 v3
==========================
生产对标：Keycloak / Okta / 阿里云 RAM

组织：星辰科技（10人），三部门
"""

import logging
import time
import uuid

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [IAM ] %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger("iam")

try:
    import jwt as pyjwt
    from jwt import PyJWTError
except ImportError:
    raise

app = FastAPI(title="IAM Identity & Access Management", version="3.0")

# ---------------------------------------------------------------------------
# 公司组织
# ---------------------------------------------------------------------------
COMPANY = "星辰科技 (StarCloud Tech)"

USERS = {
    "admin_wang": {"pwd":"admin123","name":"王总",   "email":"wang@starcloud.com","role":"admin","dept":"管理部","title":"CEO"},
    "admin_li":   {"pwd":"admin456","name":"李副总", "email":"li@starcloud.com",  "role":"admin","dept":"管理部","title":"副总裁"},
    "dev_zhang":  {"pwd":"dev123",  "name":"张工",   "email":"zhang@starcloud.com","role":"engineer","dept":"研发部","title":"高级工程师"},
    "dev_liu":    {"pwd":"dev456",  "name":"刘工",   "email":"liu@starcloud.com",  "role":"engineer","dept":"研发部","title":"工程师"},
    "dev_chen":   {"pwd":"dev789",  "name":"陈工",   "email":"chen@starcloud.com", "role":"engineer","dept":"研发部","title":"工程师"},
    "dev_zhao":   {"pwd":"dev000",  "name":"赵工",   "email":"zhao@starcloud.com", "role":"engineer","dept":"研发部","title":"实习生"},
    "fin_wu":     {"pwd":"fin123",  "name":"吴会计", "email":"wu@starcloud.com",   "role":"finance","dept":"财务部","title":"财务主管"},
    "fin_huang":  {"pwd":"fin456",  "name":"黄会计", "email":"huang@starcloud.com","role":"finance","dept":"财务部","title":"会计"},
    "ops_zhou":   {"pwd":"ops123",  "name":"周运维", "email":"zhou@starcloud.com", "role":"operator","dept":"运维部","title":"运维工程师"},
    "ops_sun":    {"pwd":"ops456",  "name":"孙运维", "email":"sun@starcloud.com",  "role":"operator","dept":"运维部","title":"运维工程师"},
}

ROLES = {
    "admin":     {"api-a:read":1,"api-a:write":1,"api-b:read":1,"api-b:write":1,"iam:admin":1},
    "engineer":  {"api-a:read":1,"api-a:write":1,"api-b:read":1,"api-b:write":0,"iam:admin":0},
    "finance":   {"api-a:read":0,"api-a:write":0,"api-b:read":1,"api-b:write":1,"iam:admin":0},
    "operator":  {"api-a:read":1,"api-a:write":0,"api-b:read":0,"api-b:write":0,"iam:admin":0},
}

IAM_SECRET = "iam-secret-starcloud-2026"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class LoginReq(BaseModel):
    username: str
    password: str

class LoginResp(BaseModel):
    session_token: str
    user_id: str
    name: str
    role: str
    dept: str
    permissions: list

class UserInfo(BaseModel):
    user_id: str; name: str; email: str
    role: str; dept: str; title: str
    permissions: list


# ---------------------------------------------------------------------------
# 会话令牌管理
# ---------------------------------------------------------------------------
_revoked_sessions: set = set()

def _create_session(user_id: str) -> str:
    u = USERS[user_id]
    perms = [k for k,v in ROLES[u["role"]].items() if v]
    now = int(time.time())
    payload = dict(iss="iam.starcloud.com", sub=user_id, name=u["name"],
                   role=u["role"], dept=u["dept"], perms=perms,
                   iat=now, exp=now+3600, jti=uuid.uuid4().hex)
    return pyjwt.encode(payload, IAM_SECRET, algorithm="HS256")

def verify_session(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    token = authorization.split(" ",1)[1]
    try:
        p = pyjwt.decode(token, IAM_SECRET, algorithms=["HS256"])
        if p.get("jti") in _revoked_sessions:
            raise HTTPException(401, "会话已吊销")
        return p
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "会话已过期")
    except PyJWTError:
        raise HTTPException(401, "无效会话")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------
@app.post("/iam/login")
async def login(req: LoginReq):
    u = USERS.get(req.username)
    if not u or u["pwd"] != req.password:
        log.warning("登录失败 | user=%s", req.username)
        raise HTTPException(401, "用户名或密码错误")
    token = _create_session(req.username)
    perms = [k for k,v in ROLES[u["role"]].items() if v]
    log.info("登录成功 | user=%s | role=%s", req.username, u["role"])
    return LoginResp(session_token=token, user_id=req.username,
                     name=u["name"], role=u["role"], dept=u["dept"],
                     permissions=perms)

@app.get("/iam/verify")
async def get_user_info(p: dict = Depends(verify_session)):
    u = USERS.get(p["sub"], {})
    return UserInfo(user_id=p["sub"], name=p["name"], email=u.get("email",""),
                    role=p["role"], dept=p["dept"], title=u.get("title",""),
                    permissions=p["perms"])

@app.get("/iam/users")
async def list_users(p: dict = Depends(verify_session)):
    if "iam:admin" not in p.get("perms", []):
        raise HTTPException(403, "仅管理员可查看")
    result = []
    for uid, u in USERS.items():
        result.append(UserInfo(user_id=uid, name=u["name"], email=u["email"],
                      role=u["role"], dept=u["dept"], title=u["title"],
                      permissions=[k for k,v in ROLES[u["role"]].items() if v]))
    return dict(company=COMPANY, total=len(result), users=result)

@app.get("/iam/me")
async def me(p: dict = Depends(verify_session)):
    return await get_user_info(p)

@app.get("/health")
async def health():
    return dict(status="ok", company=COMPANY, users=len(USERS))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=27000)
