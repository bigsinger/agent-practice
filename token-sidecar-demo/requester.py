"""
Requester v3 — 交互式多用户 Sidecar 演示
=========================================
真实场景模拟：
  1. 用户通过 IAM 登录获得会话令牌
  2. 用户向「以为的 API 地址」发请求（携带会话令牌）
  3. Sidecar 透明拦截：验证会话 → 向 Vault 取服务 JWT → 置换 → 转发
  4. 请求者全程不碰私钥、不管理服务令牌
"""
import json, logging, sys
import httpx

logging.basicConfig(level=logging.INFO,format="%(asctime)s [REQ ] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("requester")

IAM="http://localhost:27000"
SIDECAR="http://localhost:29000"

# ---------------------------------------------------------------------------
# 用户场景
# ---------------------------------------------------------------------------
SCENARIOS=[
    ("admin_wang","admin123","CEO — 完全权限"),
    ("dev_zhang","dev123","高级工程师 — 研发人员"),
    ("fin_wu","fin123","财务主管 — 财务人员"),
    ("ops_zhou","ops123","运维工程师 — 运维人员"),
]

def login(username:str,password:str)->dict|None:
    """IAM 登录"""
    try:
        r=httpx.post(f"{IAM}/iam/login",json={"username":username,"password":password},timeout=5)
        if r.status_code==200: return r.json()
        log.warning("登录失败: %s",r.json().get("detail",""))
        return None
    except Exception as e:
        log.error("登录异常: %s",e)
        return None

def call_sidecar(path:str,session_token:str)->dict:
    """通过 Sidecar 访问 API"""
    try:
        r=httpx.get(f"{SIDECAR}{path}",
                    headers={"Authorization":f"Bearer {session_token}"},timeout=10)
        return {"status":r.status_code,"body":r.json() if r.status_code<500 else r.text}
    except Exception as e:
        return {"status":0,"body":str(e)}

# ---------------------------------------------------------------------------
# 演示编排
# ---------------------------------------------------------------------------
def run_demo():
    print("="*70)
    print("  SIDECAR v3 演示 — 企业级 IAM + Vault + 透明令牌注入")
    print("="*70)
    print()

    # 1. 显示组织架构
    print("📋 公司组织：星辰科技 (StarCloud Tech)")
    print("-"*50)
    print(f"  {'用户':<14} {'姓名':<8} {'部门':<8} {'角色':<10} 密码")
    print(f"  {'----':<14} {'----':<8} {'----':<8} {'----':<10} ----")
    for uid,uname,udept,urole in [
        ("admin_wang","王总","管理部","admin"),
        ("admin_li","李副总","管理部","admin"),
        ("dev_zhang","张工","研发部","engineer"),
        ("dev_liu","刘工","研发部","engineer"),
        ("dev_chen","陈工","研发部","engineer"),
        ("dev_zhao","赵工","研发部","engineer"),
        ("fin_wu","吴会计","财务部","finance"),
        ("fin_huang","黄会计","财务部","finance"),
        ("ops_zhou","周运维","运维部","operator"),
        ("ops_sun","孙运维","运维部","operator"),
    ]:
        pwd_map={"admin_wang":"admin123","admin_li":"admin456","dev_zhang":"dev123",
                 "dev_liu":"dev456","dev_chen":"dev789","dev_zhao":"dev000",
                 "fin_wu":"fin123","fin_huang":"fin456","ops_zhou":"ops123","ops_sun":"ops456"}
        print(f"  {uid:<14} {uname:<8} {udept:<8} {urole:<10} {pwd_map[uid]}")
    print()

    # 2. 逐个用户演示
    for username,password,desc in SCENARIOS:
        print(f"\n{'─'*70}")
        print(f"👤 用户: {username} ({desc})")
        print(f"{'─'*70}")

        # 登录
        session=login(username,password)
        if not session:
            log.error("❌ 登录失败，跳过")
            continue

        print(f"  ✅ IAM 登录成功")
        print(f"     角色: {session['role']} | 部门: {session['dept']}")
        print(f"     权限: {', '.join(session['permissions'])}")
        print()

        # 访问 API-A
        print(f"  🔄 请求 → http://localhost:29000/api-a/protected-data")
        print(f"     (用户视角：直接调用 API-A，不知 Sidecar 存在)")
        r=call_sidecar("/api-a/protected-data",session["session_token"])
        if r["status"]==200:
            b=r["body"]
            print(f"  ✅ {b['service']} | 200 OK")
            print(f"     请求者: {b['requester']['name']} ({b['requester']['role']})")
            print(f"     团队: {len(b.get('team_members',[]))} 人")
        else:
            print(f"  ❌ {r['status']}: {r['body']}")
        print()

        # 访问 API-B
        print(f"  🔄 请求 → http://localhost:29000/api-b/protected-data")
        r=call_sidecar("/api-b/protected-data",session["session_token"])
        if r["status"]==200:
            b=r["body"]
            print(f"  ✅ {b['service']} | 200 OK")
            print(f"     请求者: {b['requester']['name']} ({b['requester']['role']})")
            print(f"     订单数: {b['total']}")
        else:
            print(f"  ❌ {r['status']}: {r['body']}")

    # 3. 权限拒绝演示
    print(f"\n{'─'*70}")
    print(f"🔒 权限限制演示：财务人员访问 API-A")
    print(f"{'─'*70}")
    session=login("fin_wu","fin123")
    if session:
        r=call_sidecar("/api-a/protected-data",session["session_token"])
        status_text="✅ 允许" if r["status"]==200 else "❌ 拒绝"
        # 注意：Sidecar 当前不做权限过滤，但沙箱会签发正确的 scope
        print(f"  {status_text} | 财务人员访问 API-A 的用户数据")
        print(f"  (注：沙箱对财务只签 read:orders scope，即使能访问也不含用户数据)")

    print(f"\n{'='*70}")
    print(f"  演示完成")
    print(f"  {'='*70}")
    print()
    print(f"  关键观察：")
    print(f"  · 请求者只做两件事：登录(IAM) + 发请求(Sidecar)")
    print(f"  · 服务令牌由 Sidecar 自动向 Vault 获取并注入")
    print(f"  · 请求者从不知沙箱存在，不管理任何密钥")
    print(f"  · Vault 审计日志记录了每一次令牌签发")
    print(f"  · 密钥轮换不影响正在进行的请求（旧 key 验证进行中令牌）")

if __name__=="__main__":
    run_demo()
