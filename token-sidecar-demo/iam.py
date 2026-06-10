"""
IAM v4 — 12人组织 + 6角色 + 登录页服务
==========================================
生产对标：Keycloak / Okta / 阿里云 RAM
"""
import logging, time, uuid, sqlite3, os, json
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO,format="%(asctime)s [IAM ] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("iam")
try: import jwt as pyjwt; from jwt import PyJWTError
except: raise

DB=os.path.join(os.path.dirname(__file__),"starcloud.db")
app=FastAPI(title="IAM Identity & Access Management",version="4.0")
IAM_SECRET="iam-secret-starcloud-2026"

# ── 权限模型 ──
# 0=无权 1=本部门 2=全公司
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
_perms_list=[k for k in ROLES["admin"]]

# ── 数据库操作 ──
def get_emp(username:str)->dict|None:
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees WHERE username=?",(username,))
    r=c.fetchone();conn.close()
    if not r: return None
    return dict(zip(["id","username","name","email","dept","role","title","level","phone"],r))

# ── 会话 ──
_revoked=set()
def create_session(uname:str)->str:
    u=get_emp(uname)
    perms=[k for k,v in ROLES[u["role"]].items() if v>0]
    now=int(time.time())
    p=dict(iss="iam.starcloud.com",sub=uname,name=u["name"],role=u["role"],
           dept=u["dept"],level=u["level"],perms=perms,iat=now,exp=now+3600,jti=uuid.uuid4().hex)
    return pyjwt.encode(p,IAM_SECRET,algorithm="HS256")

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
    """从 query 参数获取 session token（兼容浏览器）"""
    if not auth: raise HTTPException(401,"未登录")
    try:
        p=pyjwt.decode(auth,IAM_SECRET,algorithms=["HS256"])
        if p.get("jti") in _revoked: raise HTTPException(401,"会话已吊销")
        return p
    except pyjwt.ExpiredSignatureError: raise HTTPException(401,"会话已过期")
    except PyJWTError: raise HTTPException(401,"无效会话")

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
    if(r.ok){sessionStorage.setItem('session',d.session_token);sessionStorage.setItem('user',JSON.stringify(d));window.location.href='/portal/dashboard?token='+d.session_token}
    else{err.textContent=d.detail||'登录失败';err.style.display='block'}
  }catch(e){err.textContent='网络错误';err.style.display='block'}
})
</script></body></html>"""

from fastapi.responses import HTMLResponse

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
    perms=[k for k,v in ROLES[u["role"]].items() if v>0]
    log.info("登录成功 | user=%s | role=%s",req.username,u["role"])
    return dict(session_token=token,user_id=req.username,name=u["name"],
                role=u["role"],dept=u["dept"],permissions=perms)

@app.get("/iam/verify")
async def verify(p:dict=Depends(verify_sess)):
    u=get_emp(p["sub"])
    perms=[k for k,v in ROLES[u["role"]].items() if v>0]
    return dict(user_id=p["sub"],name=p["name"],email=u.get("email",""),
                role=p["role"],dept=p["dept"],title=u.get("title",""),
                level=u.get("level",0),permissions=perms)

@app.get("/iam/users")
async def list_users(p:dict=Depends(verify_sess)):
    if "iam:admin" not in p.get("perms",[]):
        raise HTTPException(403,"仅管理员可查看")
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees")
    rows=c.fetchall();conn.close()
    users=[]
    for r in rows:
        perms=[k for k,v in ROLES[r[5]].items() if v>0]
        users.append(dict(id=r[0],user_id=r[1],name=r[2],email=r[3],dept=r[4],
                          role=r[5],title=r[6],level=r[7],phone=r[8],permissions=perms))
    return dict(company="星辰科技",total=len(users),users=users)

@app.get("/iam/me")
async def me(p:dict=Depends(verify_sess)):
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT id,username,name,email,dept,role,title,level,phone FROM employees WHERE username=?",(p["sub"],))
    r=c.fetchone();conn.close()
    perms=[k for k,v in ROLES[r[5]].items() if v>0]
    return dict(user_id=r[1],name=r[2],email=r[3],dept=r[4],role=r[5],
                title=r[6],level=r[7],phone=r[8],permissions=perms)

def hash_pwd(pw:str)->str:
    import hashlib; return hashlib.sha256(pw.encode()).hexdigest()

@app.on_event("startup")
async def startup():
    # 确保数据库存在
    if not os.path.exists(DB):
        import seed_data; seed_data.init()
        log.info("数据库已自动初始化")
    log.info("IAM v4 就绪 | 6角色 · 12员工")

@app.get("/health")
async def health():
    return dict(status="ok",users=12,roles=ALL_ROLES)

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=27000)
