"""
IAM v5 — 12人组织 + 6角色 + Agent IAM 注册/授权/发现
======================================================
生产对标：Keycloak / Okta / 阿里云 RAM + Agent 注册中心
"""
import logging, time, uuid, sqlite3, os, json, secrets
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO,format="%(asctime)s [IAM ] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("iam")
try: import jwt as pyjwt; from jwt import PyJWTError
except: raise

DB=os.path.join(os.path.dirname(__file__),"starcloud.db")
app=FastAPI(title="IAM Identity & Access Management v5",version="5.0")
IAM_SECRET="iam-secret-starcloud-2026"

# ── 权限模型 ──
ROLES={
    "admin":    {"emp:read":2,"emp:manage":2,"salary:read":2,"salary:manage":2,
                 "order:read":2,"order:manage":2,"project:read":2,"project:manage":2,
                 "log:read":2,"iam:admin":2,"soc:manage":2,"config:manage":2},
    "engineer": {"emp:read":1,"emp:manage":0,"salary:read":0,"salary:manage":0,
                 "order:read":1,"order:manage":0,"project:read":2,"project:manage":1,
                 "log:read":0,"iam:admin":0,"soc:manage":0,"config:manage":0},
    "finance":  {"emp:read":1,"emp:manage":0,"salary:read":2,"salary:manage":1,
                 "order:read":2,"order:manage":2,"project:read":0,"project:manage":0,
                 "log:read":0,"iam:admin":0,"soc:manage":0,"config:manage":0},
    "operator": {"emp:read":1,"emp:manage":0,"salary:read":0,"salary:manage":0,
                 "order:read":0,"order:manage":0,"project:read":1,"project:manage":0,
                 "log:read":2,"iam:admin":0,"soc:manage":2,"config:manage":1},
    "hr":       {"emp:read":2,"emp:manage":2,"salary:read":0,"salary:manage":0,
                 "order:read":0,"order:manage":0,"project:read":0,"project:manage":0,
                 "log:read":0,"iam:admin":0,"soc:manage":0,"config:manage":0},
    "product":  {"emp:read":1,"emp:manage":0,"salary:read":0,"salary:manage":0,
                 "order:read":1,"order:manage":0,"project:read":2,"project:manage":0,
                 "log:read":0,"iam:admin":0,"soc:manage":0,"config:manage":0},
}
ALL_ROLES=list(ROLES.keys())
_all_perms=[k for k in ROLES["admin"]]

def full_perms(role:str)->list:
    return [k for k,v in ROLES[role].items() if v>0]

def hash_pwd(pw:str)->str:
    import hashlib; return hashlib.sha256(pw.encode()).hexdigest()

# ── 数据库操作 ──
def get_emp(username:str)->dict|None:
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees WHERE username=?",(username,))
    r=c.fetchone();conn.close()
    if not r: return None
    return dict(zip(["id","username","name","email","dept","role","title","level","phone"],r))

def get_agent(agent_id:int)->dict|None:
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT * FROM agents WHERE id=?",(agent_id,))
    r=c.fetchone();conn.close()
    if not r: return None
    cols=["id","agent_name","agent_type","client_id","client_secret_hash",
          "owner_username","status","allowed_perms","created_at","last_seen"]
    d=dict(zip(cols,r))
    if d["allowed_perms"]: d["allowed_perms"]=json.loads(d["allowed_perms"])
    return d

def get_agents_by_owner(owner:str)->list:
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT * FROM agents WHERE owner_username=?",(owner,))
    rows=c.fetchall();conn.close()
    cols=["id","agent_name","agent_type","client_id","client_secret_hash",
          "owner_username","status","allowed_perms","created_at","last_seen"]
    result=[]
    for r in rows:
        d=dict(zip(cols,r))
        if d["allowed_perms"]: d["allowed_perms"]=json.loads(d["allowed_perms"])
        d.pop("client_secret_hash",None) # 不暴露密钥
        result.append(d)
    return result

def get_all_agents()->list:
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT * FROM agents")
    rows=c.fetchall();conn.close()
    cols=["id","agent_name","agent_type","client_id","client_secret_hash",
          "owner_username","status","allowed_perms","created_at","last_seen"]
    result=[]
    for r in rows:
        d=dict(zip(cols,r))
        if d["allowed_perms"]: d["allowed_perms"]=json.loads(d["allowed_perms"])
        d.pop("client_secret_hash",None)
        result.append(d)
    return result

# ── 会话 ──
_revoked=set()
def create_session(uname:str)->str:
    u=get_emp(uname)
    perms=full_perms(u["role"])
    now=int(time.time())
    p=dict(iss="iam.starcloud.com",sub=uname,name=u["name"],role=u["role"],
           dept=u["dept"],level=u["level"],perms=perms,iat=now,exp=now+3600,jti=uuid.uuid4().hex,
           token_type="user")
    return pyjwt.encode(p,IAM_SECRET,algorithm="HS256")

def create_agent_token(agent_id:int)->tuple[str,dict]:
    """为注册Agent签发令牌，权限为其 allowed_perms 子集"""
    a=get_agent(agent_id)
    if not a: raise HTTPException(404,"Agent 不存在")
    if a["status"]!="active": raise HTTPException(403,f"Agent 状态异常: {a['status']}")
    owner=get_emp(a["owner_username"])
    if not owner: raise HTTPException(404,"所有者不存在")
    perms=a.get("allowed_perms",[])
    now=int(time.time())
    p=dict(iss="iam.starcloud.com",sub=f"agent:{a['client_id']}",
           agent_id=agent_id,agent_name=a["agent_name"],agent_type=a["agent_type"],
           owner=a["owner_username"],owner_name=owner["name"],
           owner_role=owner["role"],owner_dept=owner["dept"],
           perms=perms,iat=now,exp=now+3600,jti=uuid.uuid4().hex,
           token_type="agent")
    token=pyjwt.encode(p,IAM_SECRET,algorithm="HS256")
    # 更新 last_seen
    conn=sqlite3.connect(DB)
    conn.execute("UPDATE agents SET last_seen=? WHERE id=?",(time.strftime("%Y-%m-%d %H:%M:%S"),agent_id))
    conn.commit(); conn.close()
    return token,p

# ── 令牌验证（统一入口：用户会话 / Agent 令牌） ──
def verify_sess(authorization:str=Header(None))->dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"未登录")
    t=authorization.split(" ",1)[1]
    try:
        p=pyjwt.decode(t,IAM_SECRET,algorithms=["HS256"])
        if p.get("jti") in _revoked: raise HTTPException(401,"会话已吊销")
        return p
    except pyjwt.ExpiredSignatureError: raise HTTPException(401,"会话已过期")
    except PyJWTError: raise HTTPException(401,"无效会话")

def verify_sess_query(auth:str=Query(None,alias="token")):
    if not auth: raise HTTPException(401,"未登录")
    try:
        p=pyjwt.decode(auth,IAM_SECRET,algorithms=["HS256"])
        if p.get("jti") in _revoked: raise HTTPException(401,"会话已吊销")
        return p
    except pyjwt.ExpiredSignatureError: raise HTTPException(401,"会话已过期")
    except PyJWTError: raise HTTPException(401,"无效会话")

# ── 登录页 ──
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>星辰科技 - IAM 登录</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,'Microsoft YaHei',sans-serif}
body{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:40px;width:420px;box-shadow:0 25px 50px rgba(0,0,0,0.5)}
.logo{text-align:center;margin-bottom:30px;color:#fff}
.logo h1{font-size:24px;font-weight:700;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo p{color:rgba(255,255,255,0.5);font-size:13px;margin-top:6px}
.form-group{margin-bottom:18px}
.form-group label{display:block;color:rgba(255,255,255,0.7);font-size:13px;margin-bottom:6px}
.form-group input{width:100%;padding:12px 16px;border:1px solid rgba(255,255,255,0.1);border-radius:8px;background:rgba(255,255,255,0.05);color:#fff;font-size:14px;outline:none;transition:.2s}
.form-group input:focus{border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,0.2)}
.form-group input::placeholder{color:rgba(255,255,255,0.3)}
.btn{width:100%;padding:12px;border:none;border-radius:8px;background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;font-size:15px;font-weight:600;cursor:pointer;transition:.2s}
.btn:hover{transform:translateY(-1px);box-shadow:0 8px 25px rgba(102,126,234,0.4)}
.error{background:rgba(255,82,82,0.15);border:1px solid rgba(255,82,82,0.3);border-radius:8px;padding:10px;color:#ff5252;font-size:13px;margin-bottom:16px;display:none}
.quick-login{margin-top:20px}
.quick-login p{color:rgba(255,255,255,0.4);font-size:12px;margin-bottom:8px;text-align:center}
.quick-login .grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.quick-login .grid button{padding:6px 8px;border:1px solid rgba(255,255,255,0.1);border-radius:6px;background:rgba(255,255,255,0.05);color:rgba(255,255,255,0.6);font-size:11px;cursor:pointer;transition:.2s}
.quick-login .grid button:hover{background:rgba(255,255,255,0.1);color:#fff}
</style></head><body>
<div class="card">
  <div class="logo"><h1>✦ 星辰科技</h1><p>StarCloud Tech · IAM 统一登录</p></div>
  <div class="error" id="errMsg"></div>
  <form id="loginForm">
    <div class="form-group"><label>用户名</label><input type="text" id="username" placeholder="输入用户名" autocomplete="username"></div>
    <div class="form-group"><label>密码</label><input type="password" id="password" placeholder="输入密码" autocomplete="current-password"></div>
    <button type="submit" class="btn">登 录</button>
  </form>
  <div class="quick-login">
    <p>快速登录（测试账号）</p>
    <div class="grid">
      <button onclick="quickLogin('admin_wang','admin123')">👑 王总(CEO)</button>
      <button onclick="quickLogin('dev_zhang','dev123')">🔧 张工(研发)</button>
      <button onclick="quickLogin('fin_wu','fin123')">💰 吴会计(财务)</button>
      <button onclick="quickLogin('ops_zhou','ops123')">🛡️ 周运维(运维)</button>
      <button onclick="quickLogin('hr_xu','hr123')">👤 许HR(人事)</button>
      <button onclick="quickLogin('prod_ma','prod123')">📱 马产品(产品)</button>
    </div>
  </div>
</div>
<script>
function quickLogin(u,p){document.getElementById('username').value=u;document.getElementById('password').value=p;document.getElementById('loginForm').dispatchEvent(new Event('submit'))}
document.getElementById('loginForm').addEventListener('submit',async e=>{
  e.preventDefault();const err=document.getElementById('errMsg');err.style.display='none'
  const u=document.getElementById('username').value,p=document.getElementById('password').value
  try{
    const r=await fetch('/iam/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})})
    const d=await r.json()
    if(r.ok){sessionStorage.setItem('session',d.session_token);sessionStorage.setItem('user',JSON.stringify(d));window.location.href='http://localhost:26000/portal/dashboard?token='+d.session_token}
    else{err.textContent=d.detail||'登录失败';err.style.display='block'}
  }catch(e){err.textContent='网络错误';err.style.display='block'}
})
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return LOGIN_PAGE

class LoginReq(BaseModel):
    username: str; password: str

@app.post("/iam/login")
async def login(req: LoginReq):
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT username,password_hash FROM employees WHERE username=?",(req.username,))
    r=c.fetchone();conn.close()
    if not r or r[1]!=hash_pwd(req.password):
        log.warning("登录失败 | user=%s",req.username)
        raise HTTPException(401,"用户名或密码错误")
    token=create_session(req.username)
    u=get_emp(req.username)
    perms=full_perms(u["role"])
    log.info("登录成功 | user=%s | role=%s",req.username,u["role"])
    return dict(session_token=token,user_id=req.username,name=u["name"],
                role=u["role"],dept=u["dept"],permissions=perms)

@app.get("/iam/verify")
async def verify(p:dict=Depends(verify_sess)):
    u=get_emp(p["sub"])
    perms=full_perms(u["role"])
    return dict(user_id=p["sub"],name=p["name"],email=u.get("email",""),
                role=p["role"],dept=p["dept"],title=u.get("title",""),
                level=u.get("level",0),permissions=perms,token_type=p.get("token_type","user"))

@app.get("/iam/users")
async def list_users(p:dict=Depends(verify_sess)):
    if "iam:admin" not in p.get("perms",[]):
        raise HTTPException(403,"仅管理员可查看")
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees")
    rows=c.fetchall();conn.close()
    users=[]
    for r in rows:
        perms=full_perms(r[5])
        users.append(dict(id=r[0],user_id=r[1],name=r[2],email=r[3],dept=r[4],
                          role=r[5],title=r[6],level=r[7],phone=r[8],permissions=perms))
    return dict(company="星辰科技",total=len(users),users=users)

@app.get("/iam/me")
async def me(p:dict=Depends(verify_sess)):
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees WHERE username=?",(p["sub"],))
    r=c.fetchone();conn.close()
    perms=full_perms(r[5])
    return dict(user_id=r[1],name=r[2],email=r[3],dept=r[4],role=r[5],
                title=r[6],level=r[7],phone=r[8],permissions=perms)

# ═══════════════════════════════════════════════════════════════
# Agent IAM — Agent 注册 / 授权 / 令牌 / 发现
# ═══════════════════════════════════════════════════════════════

class RegisterAgentReq(BaseModel):
    agent_name: str
    agent_type: str = "generic"
    allowed_perms: list = []

class UpdateAgentPermsReq(BaseModel):
    allowed_perms: list = []

class AgentTokenReq(BaseModel):
    client_id: str
    client_secret: str

@app.post("/iam/agents/register")
async def register_agent(req: RegisterAgentReq, p:dict=Depends(verify_sess)):
    """员工注册自己的 Agent（权限 ≤ 员工最大权限）"""
    username=p["sub"]
    emp=get_emp(username)
    if not emp: raise HTTPException(400,"员工不存在")
    max_perms=full_perms(emp["role"])

    # 验证权限范围：不能超过员工最大权限
    for perm in req.allowed_perms:
        if perm not in max_perms:
            raise HTTPException(400,f"权限 {perm} 超出你的最大权限范围")
    if not req.allowed_perms:
        req.allowed_perms=max_perms  # 默认全量

    cid=f"agent_{uuid.uuid4().hex[:12]}"
    csecret=secrets.token_hex(16)
    now=time.strftime("%Y-%m-%d %H:%M:%S")

    conn=sqlite3.connect(DB)
    conn.execute("INSERT INTO agents (agent_name,agent_type,client_id,client_secret_hash,owner_username,status,allowed_perms,created_at) VALUES(?,?,?,?,?,?,?,?)",
                 (req.agent_name,req.agent_type,cid,hash_pwd(csecret),username,"active",json.dumps(req.allowed_perms),now))
    aid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit(); conn.close()

    log.info("Agent 注册 | id=%d name=%s owner=%s perms=%d",aid,req.agent_name,username,len(req.allowed_perms))
    return dict(agent_id=aid,client_id=cid,client_secret=csecret,  # 只在注册时返回一次
                agent_name=req.agent_name,allowed_perms=req.allowed_perms,
                warning="请妥善保管 client_secret，仅此一次显示")

@app.post("/iam/agents/{agent_id}/token")
async def agent_get_token(agent_id:int, req: AgentTokenReq):
    """Agent 用凭证换取 JWT（Client Credentials Flow）"""
    a=get_agent(agent_id)
    if not a: raise HTTPException(404,"Agent 不存在")
    if a["client_id"]!=req.client_id:
        raise HTTPException(401,"client_id 不匹配")
    if a["client_secret_hash"]!=hash_pwd(req.client_secret):
        raise HTTPException(401,"client_secret 错误")
    if a["status"]!="active":
        raise HTTPException(403,f"Agent 状态异常: {a['status']}")

    token,payload=create_agent_token(agent_id)
    owner=get_emp(a["owner_username"])
    log.info("Agent 令牌签发 | agent=%s(%d) owner=%s perms=%s",
             a["agent_name"],agent_id,a["owner_username"],payload["perms"])
    return dict(access_token=token,token_type="bearer",
                expires_in=3600,agent_id=agent_id,
                agent_name=a["agent_name"],owner=a["owner_username"],
                owner_name=owner["name"] if owner else "",
                allowed_perms=payload["perms"],
                scope=" ".join(payload["perms"]))

@app.get("/iam/agents")
async def list_my_agents(p:dict=Depends(verify_sess)):
    """查看自己的 Agent 列表"""
    username=p["sub"]
    agents=get_agents_by_owner(username)
    return dict(owner=username,total=len(agents),agents=agents)

@app.get("/iam/agents/{agent_id}")
async def get_agent_detail(agent_id:int, p:dict=Depends(verify_sess)):
    """查看某个 Agent 详情（仅拥有者和管理员可看）"""
    a=get_agent(agent_id)
    if not a: raise HTTPException(404,"Agent 不存在")
    if a["owner_username"]!=p["sub"] and "iam:admin" not in p.get("perms",[]):
        raise HTTPException(403,"无权查看此 Agent")
    a.pop("client_secret_hash",None)
    return a

@app.post("/iam/agents/{agent_id}/permissions")
async def update_agent_permissions(agent_id:int, req: UpdateAgentPermsReq,
                                   p:dict=Depends(verify_sess)):
    """员工更新自己 Agent 的权限范围（仍须 ≤ 员工最大权限）"""
    a=get_agent(agent_id)
    if not a: raise HTTPException(404,"Agent 不存在")
    if a["owner_username"]!=p["sub"]:
        raise HTTPException(403,"只能修改自己的 Agent")
    emp=get_emp(p["sub"])
    max_perms=full_perms(emp["role"])
    for perm in req.allowed_perms:
        if perm not in max_perms:
            raise HTTPException(400,f"权限 {perm} 超出你的最大权限范围")

    conn=sqlite3.connect(DB)
    conn.execute("UPDATE agents SET allowed_perms=? WHERE id=?",(json.dumps(req.allowed_perms),agent_id))
    conn.commit(); conn.close()
    log.info("Agent 权限更新 | id=%d perms=%s",agent_id,req.allowed_perms)
    return dict(agent_id=agent_id,allowed_perms=req.allowed_perms)

@app.post("/iam/agents/{agent_id}/revoke")
async def revoke_agent(agent_id:int, p:dict=Depends(verify_sess)):
    """吊销 Agent（拥有者或管理员）"""
    a=get_agent(agent_id)
    if not a: raise HTTPException(404,"Agent 不存在")
    if a["owner_username"]!=p["sub"] and "iam:admin" not in p.get("perms",[]):
        raise HTTPException(403,"无权吊销此 Agent")

    conn=sqlite3.connect(DB)
    conn.execute("UPDATE agents SET status='revoked' WHERE id=?",(agent_id,))
    conn.commit(); conn.close()
    log.warning("Agent 吊销 | id=%d name=%s by=%s",agent_id,a["agent_name"],p["sub"])
    return dict(agent_id=agent_id,status="revoked")

@app.get("/iam/agents/discovery/all")
async def agent_discovery(p:dict=Depends(verify_sess)):
    """Agent 发现 — 查看所有已注册/未注册 Agent（仅管理员/运维）"""
    if "iam:admin" not in p.get("perms",[]) and "soc:manage" not in p.get("perms",[]):
        raise HTTPException(403,"仅管理员或运维可查看 Agent 全景")
    all_agents=get_all_agents()
    # 统计分析
    active=[a for a in all_agents if a["status"]=="active"]
    revoked=[a for a in all_agents if a["status"]=="revoked"]
    pending=[a for a in all_agents if a["status"]=="pending"]
    unknown=[a for a in all_agents if a["owner_username"]=="unknown"]
    by_role={}
    for a in all_agents:
        emp=get_emp(a["owner_username"])
        role=emp["role"] if emp else "unknown"
        by_role.setdefault(role,[]).append(a["agent_name"])
    # 检测未在数据库中的 Agent（模拟扫描到的新Agent）
    new_agent_activity=[a for a in all_agents if a.get("last_seen") and not a.get("last_seen","").startswith("2026")]

    return dict(
        company="星辰科技 · Agent 注册中心",
        total=len(all_agents),
        active=len(active),
        revoked=len(revoked),
        pending=len(pending),
        unregistered=len(unknown),
        agents=all_agents,
        summary_by_role=by_role,
        security_note="仅已注册并 active 的 Agent 可访问业务 API"
    )

@app.get("/iam/agents/discovery/scan")
async def agent_scan(p:dict=Depends(verify_sess)):
    """模拟 Agent 发现扫描 — 检测网络中的活跃 Agent（仅管理员/运维）"""
    if "iam:admin" not in p.get("perms",[]) and "soc:manage" not in p.get("perms",[]):
        raise HTTPException(403,"仅管理员或运维可扫描")
    all_agents=get_all_agents()
    active_registered=[a for a in all_agents if a["status"]=="active"]
    unregistered=[a for a in all_agents if a["status"]=="pending" or a["owner_username"]=="unknown"]
    return dict(
        scan_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        networks=["10.0.0.0/24","10.0.1.0/24"],
        detected_total=len(all_agents),
        registered=len(active_registered),
        unregistered=len(unregistered),
        unregistered_list=[dict(id=a["id"],agent_name=a["agent_name"],
                                agent_type=a["agent_type"],status=a["status"],
                                owner=a["owner_username"]) for a in unregistered],
        recommendation="检测到未注册 Agent，建议立即处理"
    )

@app.get("/iam/introspect")
async def introspect_token(authorization:str=Header(None)):
    """统一令牌查验 — 用于 Sidecar 验证任意 Bearer token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"无令牌")
    t=authorization.split(" ",1)[1]
    try:
        p=pyjwt.decode(t,IAM_SECRET,algorithms=["HS256"])
        if p.get("jti") in _revoked:
            return dict(active=False,reason="已吊销")
        token_type=p.get("token_type","user")
        base=dict(active=True,exp=p.get("exp"),iat=p.get("iat"),
                  jti=p.get("jti"),token_type=token_type)
        if token_type=="agent":
            base.update(agent_id=p["agent_id"],agent_name=p["agent_name"],
                       agent_type=p["agent_type"],owner=p["owner"],
                       owner_name=p["owner_name"],owner_role=p["owner_role"],
                       owner_dept=p["owner_dept"])
        else:
            base.update(user_id=p["sub"],name=p.get("name",""),
                       role=p.get("role",""),dept=p.get("dept",""),
                       level=p.get("level",0))
        base["permissions"]=p.get("perms",[])
        return base
    except pyjwt.ExpiredSignatureError:
        return dict(active=False,reason="已过期")
    except PyJWTError:
        return dict(active=False,reason="无效令牌")

@app.get("/health")
async def health():
    return dict(status="ok",users=12,roles=ALL_ROLES,version="v5-agent-iam")

@app.on_event("startup")
async def startup():
    if not os.path.exists(DB):
        import seed_data; seed_data.init()
        log.info("数据库已自动初始化")
    log.info("IAM v5 就绪 | 6角色 · 12员工 · Agent IAM")

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=27000)
