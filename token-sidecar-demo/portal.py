"""
Portal v4 — Web 管理门户
=========================
提供：登录页、角色仪表盘、SOC 安全运维中心、员工管理、权限展示
所有数据通过 Sidestream（全架构保留）。
"""
import httpx, json, logging, asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO,format="%(asctime)s [PORT] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("portal")

IAM="http://localhost:27000"
app=FastAPI(title="星辰科技管理门户",version="4.0")

# ── 工具 ──
async def api_get(path:str,token:str=""):
    headers={}
    if token: headers["Authorization"]=f"Bearer {token}"
    async with httpx.AsyncClient() as c:
        return await c.get(f"{IAM}{path}",headers=headers,timeout=10)

# ── 页面全局模板 ──
PAGE_TOP=r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TITLE_HERE - 星辰科技管理门户</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,'Microsoft YaHei',sans-serif}
body{background:#0f0f1a;color:#e0e0e0;min-height:100vh}
.topbar{background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.06);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between}
.topbar .logo{font-size:18px;font-weight:700;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.topbar .user-info{display:flex;align-items:center;gap:12px;font-size:13px;color:rgba(255,255,255,0.5)}
.topbar .user-info .role-badge{padding:3px 10px;border-radius:12px;font-size:11px}
.badge-admin{background:rgba(102,126,234,0.2);color:#667eea}
.badge-engineer{background:rgba(76,175,80,0.2);color:#4caf50}
.badge-finance{background:rgba(255,193,7,0.2);color:#ffc107}
.badge-operator{background:rgba(0,188,212,0.2);color:#00bcd4}
.badge-hr{background:rgba(156,39,176,0.2);color:#9c27b0}
.badge-product{background:rgba(255,152,0,0.2);color:#ff9800}
.container{max-width:1200px;margin:0 auto;padding:24px}
.dashboard{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:20px}
.card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:20px;transition:.2s}
.card:hover{border-color:rgba(255,255,255,0.12);background:rgba(255,255,255,0.05)}
.card h3{font-size:14px;font-weight:600;color:rgba(255,255,255,0.5);margin-bottom:8px}
.card .value{font-size:28px;font-weight:700}
.card .desc{font-size:12px;color:rgba(255,255,255,0.3);margin-top:4px}
h2{font-size:20px;font-weight:700;margin:24px 0 8px}
h2:first-child{margin-top:0}
table{width:100%;border-collapse:collapse;margin-top:12px}
th{text-align:left;padding:10px 12px;font-size:12px;color:rgba(255,255,255,0.4);border-bottom:1px solid rgba(255,255,255,0.06);text-transform:uppercase;letter-spacing:1px}
td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.03)}
tr:hover td{background:rgba(255,255,255,0.02)}
.status{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.status-active{background:rgba(76,175,80,0.15);color:#4caf50}
.status-pending{background:rgba(255,193,7,0.15);color:#ffc107}
.status-paid{background:rgba(76,175,80,0.15);color:#4caf50}
.status-shipped{background:rgba(0,188,212,0.15);color:#00bcd4}
.status-critical{background:rgba(244,67,54,0.2);color:#f44336}
.status-warning{background:rgba(255,152,0,0.2);color:#ff9800}
.status-info{background:rgba(33,150,243,0.2);color:#2196f3}
.nav{display:flex;gap:16px;margin:16px 0}
.nav a{padding:8px 16px;border-radius:8px;font-size:13px;color:rgba(255,255,255,0.5);text-decoration:none;transition:.2s}
.nav a:hover{background:rgba(255,255,255,0.05);color:#fff}
.btn-logout{padding:6px 14px;border:1px solid rgba(255,255,255,0.1);border-radius:6px;background:transparent;color:rgba(255,255,255,0.5);font-size:12px;cursor:pointer;transition:.2s}
.btn-logout:hover{border-color:#f44336;color:#f44336}
.green{color:#4caf50}
.red{color:#f44336}
.orange{color:#ff9800}
.perm-table td:first-child{font-weight:600;min-width:160px}
.perm-y{color:#4caf50} .perm-n{color:rgba(255,255,255,0.2)}
.empty{color:rgba(255,255,255,0.3);text-align:center;padding:40px;font-size:14px}
</style></head><body>
<div class="topbar">
  <div class="logo">✦ 星辰科技管理系统</div>
  <div class="user-info">
    <span id="userName"></span>
    <span class="role-badge" id="roleBadge"></span>
    <button class="btn-logout" onclick="logout()">退出</button>
  </div>
</div>
<script>
const TOKEN=new URLSearchParams(location.search).get('token')||'';
if(TOKEN)sessionStorage.setItem('session',TOKEN);
const TOK=sessionStorage.getItem('session')||'';
if(!TOK&&location.pathname!='/portal/login')location.href='/portal/login';
async function loadUser(){try{
  const r=await fetch('/portal/api/me?token='+TOK);
  if(r.ok){const d=await r.json();
    document.getElementById('userName').textContent=d.name+' ('+d.user_id+')';
    document.getElementById('roleBadge').textContent=d.role;
    const badge=document.getElementById('roleBadge');
    badge.className='role-badge badge-'+d.role;
  }
}catch(e){}}
function logout(){sessionStorage.removeItem('session');location.href='/portal/login'}
loadUser();
</script>
<div class="container">"""

PAGE_BOTTOM="""</div></body></html>"""

# ── 页面路由 ──

@app.get("/portal/login",response_class=HTMLResponse)
async def portal_login():
    r=await api_get("/","")
    return r.text if hasattr(r,'text') else (await api_get("/","")).text

@app.get("/portal/dashboard",response_class=HTMLResponse)
async def dashboard(request:Request):
    token=request.query_params.get("token","") or ""
    if not token: return HTMLResponse("<script>location.href='/portal/login'</script>")
    try:
        r=await api_get("/iam/me",token)
        u=r.json()
    except: return HTMLResponse("<script>location.href='/portal/login'</script>")
    role=u["role"];dept=u["dept"];name=u["name"]

    html=PAGE_TOP.replace("TITLE_HERE", "仪表盘")
    html+=f'<div class="nav"><a href="/portal/dashboard?token={token}">📊 仪表盘</a>'
    html+=f'<a href="/portal/employees?token={token}">👥 员工</a>'
    html+=f'<a href="/portal/orders?token={token}">📦 订单</a>'
    html+=f'<a href="/portal/projects?token={token}">📋 项目</a>'
    if "soc:manage" in u.get("permissions",[]):
        html+=f'<a href="/portal/soc?token={token}">🛡️ 安全运维</a>'
    html+='</div>'

    html+=f'<h2>👋 欢迎回来，{name}</h2>'
    html+=f'<p style="color:rgba(255,255,255,0.4);font-size:13px">部门：{dept} ｜ 角色：{role}</p>'

    # 角色专属仪表盘
    if role=="admin":
        html+=admin_dashboard(token)
    elif role=="engineer":
        html+=engineer_dashboard(token,u)
    elif role=="finance":
        html+=finance_dashboard(token)
    elif role=="operator":
        html+=operator_dashboard(token)
    elif role=="hr":
        html+=hr_dashboard(token)
    elif role=="product":
        html+=product_dashboard(token,u)

    html+=PAGE_BOTTOM
    return HTMLResponse(html)

@app.get("/portal/employees",response_class=HTMLResponse)
async def employees_page(request:Request):
    token=request.query_params.get("token","") or ""
    if not token: return HTMLResponse("<script>location.href='/portal/login'</script>")
    html=PAGE_TOP.replace("TITLE_HERE", "员工管理")
    html+=f'<div class="nav"><a href="/portal/dashboard?token={token}">⬅ 返回</a></div>'
    html+=f'<h2>👥 员工列表</h2>'
    try:
        r=await api_get("/iam/users",token)
        if r.status_code!=200:
            html+=f'<div class="empty">{r.json().get("detail","无权访问")}</div>'
            html+=PAGE_BOTTOM
            return HTMLResponse(html)
        data=r.json()
        html+='<table><tr><th>用户名</th><th>姓名</th><th>部门</th><th>角色</th><th>职称</th><th>等级</th></tr>'
        for u in data["users"]:
            html+=f'<tr><td>{u["user_id"]}</td><td>{u["name"]}</td><td>{u["dept"]}</td>'
            html+=f'<td><span class="role-badge badge-{u["role"]}">{u["role"]}</span></td>'
            html+=f'<td>{u["title"]}</td><td>L{u["level"]}</td></tr>'
        html+='</table>'
    except Exception as e:
        html+=f'<div class="empty">加载失败: {e}</div>'
    html+=PAGE_BOTTOM
    return HTMLResponse(html)

@app.get("/portal/orders",response_class=HTMLResponse)
async def orders_page(request:Request):
    token=request.query_params.get("token","") or ""
    if not token: return HTMLResponse("<script>location.href='/portal/login'</script>")
    html=PAGE_TOP.replace("TITLE_HERE", "订单管理")
    html+=f'<div class="nav"><a href="/portal/dashboard?token={token}">⬅ 返回</a></div>'
    html+=f'<h2>📦 订单列表</h2>'
    html+='<table><tr><th>订单号</th><th>客户</th><th>金额</th><th>状态</th><th>部门</th><th>创建人</th><th>时间</th></tr>'
    orders_data=[
        ("ORD-20260601-001","张三",299,"paid","管理部","admin_wang","06-01 09:30"),
        ("ORD-20260601-002","李四",1599.5,"shipped","研发部","dev_zhang","06-01 10:15"),
        ("ORD-20260602-003","王五",89.9,"pending","财务部","fin_wu","06-02 14:00"),
        ("ORD-20260603-001","赵六",4599,"paid","管理部","admin_li","06-03 08:45"),
        ("ORD-20260604-002","孙七",12000,"shipped","研发部","dev_liu","06-04 11:20"),
        ("ORD-20260605-003","周八",350,"pending","运维部","ops_zhou","06-05 16:30"),
        ("ORD-20260606-001","吴九",8800,"paid","产品部","prod_ma","06-06 09:00"),
        ("ORD-20260607-002","郑十",25600,"shipped","管理部","admin_wang","06-07 13:45"),
    ]
    for o in orders_data:
        html+=f'<tr><td>{o[0]}</td><td>{o[1]}</td><td>¥{o[2]:,.2f}</td>'
        html+=f'<td><span class="status status-{o[3]}">{o[3]}</span></td>'
        html+=f'<td>{o[4]}</td><td>{o[5]}</td><td>{o[6]}</td></tr>'
    html+='</table>'
    html+=PAGE_BOTTOM
    return HTMLResponse(html)

@app.get("/portal/projects",response_class=HTMLResponse)
async def projects_page(request:Request):
    token=request.query_params.get("token","") or ""
    if not token: return HTMLResponse("<script>location.href='/portal/login'</script>")
    html=PAGE_TOP.replace("TITLE_HERE", "项目管理")
    html+=f'<div class="nav"><a href="/portal/dashboard?token={token}">⬅ 返回</a></div>'
    html+=f'<h2>📋 项目列表</h2>'
    html+='<table><tr><th>项目名</th><th>负责人</th><th>预算</th><th>状态</th><th>截止日</th></tr>'
    projs=[
        ("AI Agent Platform","dev_zhang",300000,"active","2026-09-30"),
        ("IAM 统一认证","dev_liu",150000,"active","2026-08-15"),
        ("数据中台 v3","dev_zhang",500000,"planning","2027-01-01"),
        ("财务系统升级","fin_wu",200000,"active","2026-10-01"),
        ("运维监控平台","ops_zhou",180000,"active","2026-07-01"),
        ("官网重构","prod_ma",80000,"pending","2026-11-01"),
    ]
    for p in projs:
        html+=f'<tr><td>{p[0]}</td><td>{p[1]}</td><td>¥{p[2]:,}</td>'
        html+=f'<td><span class="status status-{p[3]}">{p[3]}</span></td><td>{p[4]}</td></tr>'
    html+='</table>'
    html+=PAGE_BOTTOM
    return HTMLResponse(html)

@app.get("/portal/soc",response_class=HTMLResponse)
async def soc_page(request:Request):
    """安全运维中心（SOC）"""
    token=request.query_params.get("token","") or ""
    if not token: return HTMLResponse("<script>location.href='/portal/login'</script>")
    try:
        r=await api_get("/iam/me",token)
        u=r.json()
        if "soc:manage" not in u.get("permissions",[]):
            return HTMLResponse(f"<script>alert('无权限访问安全运维中心');location.href='/portal/dashboard?token={token}'</script>")
    except:
        return HTMLResponse("<script>location.href='/portal/login'</script>")

    html=PAGE_TOP.replace("TITLE_HERE", "安全运维中心")
    html+=f'<div class="nav"><a href="/portal/dashboard?token={token}">⬅ 返回仪表盘</a></div>'
    html+=f'<h2>🛡️ 安全运维中心 (SOC)</h2>'
    html+=f'<p style="color:rgba(255,255,255,0.4);font-size:13px">安全运维工程师专用 · 星辰科技</p>'

    # 安全概览卡片
    html+='<div class="dashboard">'
    html+=f'<div class="card"><h3>安全日志总数</h3><div class="value">15</div><div class="desc">今日已记录</div></div>'
    html+=f'<div class="card"><h3>⚠️ 高危事件</h3><div class="value red">2</div><div class="desc">需立即处理</div></div>'
    html+=f'<div class="card"><h3>活跃会话</h3><div class="value green">6</div><div class="desc">当前在线用户</div></div>'
    html+=f'<div class="card"><h3>系统状态</h3><div class="value green">正常</div><div class="desc">所有服务在线</div></div>'
    html+='</div>'

    # 权限管控概览
    html+=f'<h2 style="margin-top:32px">🔐 权限管控概览</h2>'
    html+='<table class="perm-table">'
    html+='<tr><th>角色</th><th>emp:read</th><th>salary:read</th><th>order:read</th><th>project:read</th><th>log:read</th><th>soc:manage</th></tr>'
    perms_map=[("admin","✅","✅","✅","✅","✅","✅"),("engineer","✅本部门","❌","✅本部门","✅","❌","❌"),
               ("finance","✅本部门","✅","✅","❌","❌","❌"),("operator","✅本部门","❌","❌","✅本部门","✅","✅"),
               ("hr","✅","❌","❌","❌","❌","❌"),("product","✅本部门","❌","✅本部门","✅","❌","❌")]
    coll=["emp","salary","order","project","log","soc"]
    for row in perms_map:
        html+=f'<tr><td>{row[0]}</td>'
        for i in range(6):
            v=row[i+1]
            cls="perm-y" if "✅" in v else "perm-n"
            html+=f'<td class="{cls}">{v}</td>'
        html+='</tr>'
    html+='</table>'

    # 安全日志
    html+=f'<h2 style="margin-top:32px">📋 安全审计日志</h2>'
    html+='<table><tr><th>时间</th><th>类型</th><th>用户</th><th>IP</th><th>详情</th><th>级别</th></tr>'
    logs=[
        ("06-10 09:15","login","hr_xu","10.0.0.40","许HR登录系统","info"),
        ("06-10 09:10","config.change","ops_zhou","10.0.0.5","修改防火墙规则：开放8443端口","critical"),
        ("06-10 09:05","login.failed","dev_zhao","10.0.0.24","密码连续错误5次（锁定时）","warning"),
        ("06-10 09:00","token.issue","sidecar-02","10.0.0.101","为api-b签发令牌","info"),
        ("06-10 08:55","system","system","-","数据库自动备份完成","info"),
        ("06-10 08:50","login","ops_zhou","10.0.0.5","运维工程师登录","info"),
        ("06-10 08:45","bruteforce","10.0.0.200","10.0.0.200","SSH爆破攻击150次/分钟","critical"),
        ("06-10 08:40","api.access","fin_wu","10.0.0.30","GET /api-b 403权限不足","warning"),
        ("06-10 08:35","key.rotate","ops_zhou","10.0.0.5","触发密钥轮换","info"),
        ("06-10 08:30","token.revoke","ops_zhou","10.0.0.5","手动吊销异常令牌","warning"),
    ]
    for l in logs:
        html+=f'<tr><td>{l[0]}</td><td>{l[1]}</td><td>{l[2]}</td><td>{l[3]}</td><td>{l[4]}</td>'
        html+=f'<td><span class="status status-{l[5]}">{l[5]}</span></td></tr>'
    html+='</table>'

    # 密钥状态
    html+=f'<h2 style="margin-top:32px">🔑 密钥与令牌状态</h2>'
    html+='<div class="dashboard">'
    html+=f'<div class="card"><h3>当前签发密钥</h3><div class="value">key-8a528624</div><div class="desc">RSA-2048 · 轮换历史</div></div>'
    html+=f'<div class="card"><h3>已吊销令牌</h3><div class="value orange">1</div><div class="desc">jti=abc123</div></div>'
    html+=f'<div class="card"><h3>今日签发量</h3><div class="value">24</div><div class="desc">Sidecar令牌签发</div></div>'
    html+='</div>'

    html+=PAGE_BOTTOM
    return HTMLResponse(html)

# ── API 代理（供前端调用） ──

@app.get("/portal/api/me")
async def portal_me(token:str=""):
    r=await api_get("/iam/me",token)
    return r.json() if r.status_code==200 else {"error":"unauthorized"}

# ── 角色仪表盘函数 ──

def admin_dashboard(token:str):
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>👥 总员工</h3><div class="value">12</div><div class="desc">6大部门</div></div>'
    h+=f'<div class="card"><h3>💰 总预算</h3><div class="value">¥2,950万</div><div class="desc">年度部门预算</div></div>'
    h+=f'<div class="card"><h3>📦 总订单</h3><div class="value">8</div><div class="desc">总金额 ¥53,837</div></div>'
    h+=f'<div class="card"><h3>📋 在研项目</h3><div class="value">4</div><div class="desc">活跃项目数</div></div>'
    h+='</div>'
    h+='<h2>最近操作</h2>'
    h+='<table><tr><th>时间</th><th>事件</th><th>用户</th></tr>'
    h+='<tr><td>09:10</td><td>防火墙规则变更</td><td>ops_zhou</td></tr>'
    h+='<tr><td>08:50</td><td>安全巡检</td><td>ops_zhou</td></tr>'
    h+='<tr><td>08:35</td><td>密钥轮换</td><td>系统</td></tr>'
    h+='<tr><td>08:20</td><td>异常登录告警</td><td>系统</td></tr>'
    h+='</table>'
    return h

def engineer_dashboard(token:str, u:dict):
    level=u.get("level",1)
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>📋 我的项目</h3><div class="value">{3 if level>=4 else 2 if level>=3 else 1 if level>=2 else 0}</div><div class="desc">L{level} 工程师可见范围</div></div>'
    h+=f'<div class="card"><h3>👥 研发团队</h3><div class="value">4</div><div class="desc">张/刘/陈/赵</div></div>'
    h+=f'<div class="card"><h3>💰 项目预算</h3><div class="value">¥113万</div><div class="desc">负责项目总预算</div></div>'
    h+='</div>'
    h+='<h2>我的项目</h2>'
    h+='<table><tr><th>项目名</th><th>角色</th><th>预算</th><th>状态</th></tr>'
    if level>=4:
        h+='<tr><td>AI Agent Platform</td><td>核心成员</td><td>¥300,000</td><td><span class="status status-active">进行中</span></td></tr>'
        h+='<tr><td>IAM 统一认证</td><td>负责人</td><td>¥150,000</td><td><span class="status status-active">进行中</span></td></tr>'
        h+='<tr><td>数据中台 v3</td><td>规划</td><td>¥500,000</td><td><span class="status status-pending">规划中</span></td></tr>'
    elif level>=2:
        h+='<tr><td>IAM 统一认证</td><td>成员</td><td>¥150,000</td><td><span class="status status-active">进行中</span></td></tr>'
    else:
        h+='<tr><td colspan="4" class="empty">暂无项目权限</td></tr>'
    h+='</table>'
    return h

def finance_dashboard(token:str):
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>💰 本月营收</h3><div class="value">¥53,837</div><div class="desc">8笔订单</div></div>'
    h+=f'<div class="card"><h3>🏦 薪资总额</h3><div class="value">¥83.1万</div><div class="desc">12人月度</div></div>'
    h+=f'<div class="card"><h3>📊 预算执行</h3><div class="value">68%</div><div class="desc">年度进度</div></div>'
    h+='</div>'
    h+='<h2>薪资概览（敏感数据）</h2>'
    h+='<table><tr><th>姓名</th><th>部门</th><th>基本工资</th><th>年终奖</th><th>税率</th></tr>'
    salaries=[("王总","管理部","180,000","360,000","45%"),("李副总","管理部","120,000","240,000","35%"),
              ("张工","研发部","65,000","130,000","25%"),("吴会计","财务部","50,000","100,000","20%")]
    for s in salaries:
        h+=f'<tr><td>{s[0]}</td><td>{s[1]}</td><td>¥{s[2]}</td><td>¥{s[3]}</td><td>{s[4]}</td></tr>'
    h+='</table>'
    return h

def operator_dashboard(token:str):
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>🛡️ 安全告警</h3><div class="value red">2</div><div class="desc">待处理</div></div>'
    h+=f'<div class="card"><h3>🔑 令牌签发</h3><div class="value green">24</div><div class="desc">今日</div></div>'
    h+=f'<div class="card"><h3>⚙️ 系统运行</h3><div class="value green">正常</div><div class="desc">5/5 服务在线</div></div>'
    h+='</div>'
    h+=f'<h2>服务状态</h2>'
    h+='<table><tr><th>服务</th><th>端口</th><th>状态</th></tr>'
    for s in [("IAM",27000,"✅"),("Vault",28001,"✅"),("API-A",28100,"✅"),("API-B",28200,"✅"),("Sidecar",29000,"✅")]:
        h+=f'<tr><td>{s[0]}</td><td>{s[1]}</td><td class="green">{s[2]}</td></tr>'
    h+='</table>'
    return h

def hr_dashboard(token:str):
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>👥 员工总数</h3><div class="value">12</div><div class="desc">6部门</div></div>'
    h+=f'<div class="card"><h3>📋 人事变动</h3><div class="value">0</div><div class="desc">本月无变动</div></div>'
    h+=f'<div class="card"><h3>🎯 招聘中</h3><div class="value">2</div><div class="desc">高级工程师/产品经理</div></div>'
    h+='</div>'
    h+='<h2>组织架构（人事可见）</h2>'
    h+='<table><tr><th>姓名</th><th>部门</th><th>职位</th><th>等级</th><th>电话</th></tr>'
    emps=[("王总","管理部","CEO",5,"138****1001"),("李副总","管理部","副总裁",4,"138****1002"),
           ("张工","研发部","高级工程师",5,"138****1003"),("刘工","研发部","工程师",4,"138****1004"),
           ("许HR","人事部","人事主管",4,"138****1011")]
    for e in emps:
        h+=f'<tr><td>{e[0]}</td><td>{e[1]}</td><td>{e[2]}</td><td>L{e[3]}</td><td>{e[4]}</td></tr>'
    h+='</table>'
    return h

def product_dashboard(token:str, u:dict):
    h=f'<div class="dashboard">'
    h+=f'<div class="card"><h3>📋 产品项目</h3><div class="value">2</div><div class="desc">参与中</div></div>'
    h+=f'<div class="card"><h3>📦 订单关联</h3><div class="value">1</div><div class="desc">产品部订单</div></div>'
    h+='</div>'
    h+='<h2>我的项目</h2>'
    h+='<table><tr><th>项目名</th><th>状态</th><th>角色</th></tr>'
    h+='<tr><td>AI Agent Platform</td><td><span class="status status-active">进行中</span></td><td>产品负责人</td></tr>'
    h+='<tr><td>数据中台 v3</td><td><span class="status status-pending">规划中</span></td><td>需求评审</td></tr>'
    h+='<tr><td>官网重构</td><td><span class="status status-pending">待启动</span></td><td>项目经理</td></tr>'
    h+='</table>'
    return h

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=26000)
