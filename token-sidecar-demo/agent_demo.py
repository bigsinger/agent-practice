"""
agent_demo.py — Agent IAM 场景模拟
=====================================
模拟 12 员工各自 1-2 个 Agent 的不同授权/访问行为
"""
import httpx, json, time, sys

IAM="http://localhost:27000"
SIDECAR="http://localhost:29000"
PORTAL="http://localhost:26000"

def log(tag, msg): print(f"[{tag:12s}] {msg}")

# 预置 Agent 凭据（来自 seed_data.py）
PRESET_AGENTS = {
    # 张工的代码审查助手（工程全量权限）
    "dev_zhang": {"id":4, "client_id":"agent_zhang_code", "secret":"sec_zhang_code123"},
    # 陈工的测试自动化（只读 project）
    "dev_chen":  {"id":7, "client_id":"agent_chen_qa", "secret":"sec_chen_qa123"},
    # 吴会计的账务机器人（财务全量）
    "fin_wu":    {"id":9, "client_id":"agent_wu_acct", "secret":"sec_wu_acct789"},
    # 周运维的巡检机器人（运维全量）
    "ops_zhou":  {"id":12,"client_id":"agent_zhou_sec","secret":"sec_zhou_sec789"},
    # 未注册 Agent（无有效凭据）
    "ghost":     {"id":17,"client_id":"ghost_crawler", "secret":"no_auth_xxx"},
}

def get_agent_token(agent_key):
    """Agent 用 client_id + secret 换取 JWT"""
    a = PRESET_AGENTS.get(agent_key)
    if not a: return None
    r = httpx.post(f"{IAM}/iam/agents/{a['id']}/token",
                   json={"client_id": a["client_id"], "client_secret": a["secret"]}, timeout=5)
    if r.status_code == 200:
        return r.json()["access_token"]
    return None

def call_sidecar(route, token):
    """通过 Sidecar 访问业务 API"""
    h = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.get(f"{SIDECAR}{route}", headers=h, timeout=5)
    return r.status_code, r.json() if r.status_code < 500 else r.text

def login_employee(username, password):
    """员工登录获取会话 token"""
    r = httpx.post(f"{IAM}/iam/login",
                   json={"username": username, "password": password}, timeout=5)
    return r.json().get("session_token") if r.status_code == 200 else None

def register_new_agent(user_token, name, atype, perms):
    """注册新 Agent（模拟员工在 Portal 操作）"""
    r = httpx.post(f"{IAM}/iam/agents/register",
                   headers={"Authorization": f"Bearer {user_token}"},
                   json={"agent_name": name, "agent_type": atype, "allowed_perms": perms}, timeout=5)
    return r.json() if r.status_code == 200 else r.json()

# ═══════════════════════════════════════
# 场景模拟
# ═══════════════════════════════════════

warn = "\n" + "="*65 + "\n"
info = "\n" + "-"*65

def main():
    print("="*65)
    print("  星辰科技 · Agent IAM 安全演练")
    print("  场景：Agent 发现 + 身份认证 + 权限管控")
    print("="*65)

    passed = 0
    failed = 0

    def check(name, ok):
        nonlocal passed, failed
        if ok:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")
            failed += 1

    # ── 场景 1：已注册 Agent 正常访问（张工的代码助手）──
    print(info)
    print("  📋 场景1: 已授权 Agent 访问业务 API")
    print("    Agent: 张工-代码审查助手 (engineer 全量权限)")
    print("-"*65)

    tok = get_agent_token("dev_zhang")
    check("Agent 令牌签发成功", bool(tok))

    code, data = call_sidecar("/api-a/protected-data", tok)
    check(f"访问 API-A (用户数据) → {code}", code == 200)
    if code == 200:
        print(f"    响应: {json.dumps(data.get('requester',{}), ensure_ascii=False)}")

    code, data = call_sidecar("/api-b/protected-data", tok)
    check(f"访问 API-B (订单数据) → {code}", code == 200)
    if code == 200:
        print(f"    响应: {json.dumps(data.get('orders',[])[:1], ensure_ascii=False)}")

    # ── 场景 2：权限不足的 Agent 访问受限 API ──
    print(info)
    print("  📋 场景2: 权限不足的 Agent 被拒绝")
    print("    Agent: 陈工-测试自动化 (只有 project:read)")
    print("    尝试访问 API-A (需要 emp:read) → 应返回 403")
    print("-"*65)

    tok2 = get_agent_token("dev_chen")
    check("Agent 令牌签发成功", bool(tok2))

    code, data = call_sidecar("/api-a/protected-data", tok2)
    check(f"访问 API-A (权限不足) → {code}", code == 403)
    if code == 403:
        print(f"    拒绝原因: {data.get('detail','') if isinstance(data,dict) else data}")

    code, data = call_sidecar("/api-b/protected-data", tok2)
    check(f"访问 API-B (也无权限) → {code}", code == 403)

    # ── 场景 3：未注册 Agent 被拦截 ──
    print(info)
    print("  📋 场景3: 未注册/幽灵 Agent 被拦截")
    print("    Agent: 幽灵爬虫-7788 (未注册, pending)")
    print("-"*65)

    tok3 = get_agent_token("ghost")
    check("幽灵 Agent 令牌签发失败（状态异常）", not tok3)

    # 无令牌访问
    code, data = call_sidecar("/api-a/protected-data", None)
    if not isinstance(data, dict): data = {}
    check(f"无令牌访问 → {code}", code in (401, 403))

    # ── 场景 4：员工通过 Portal 管理自己的 Agent ──
    print(info)
    print("  📋 场景4: 员工管理自己的 Agent")
    print("    张工登录 → 查看 Agent 列表")
    print("-"*65)

    utok = login_employee("dev_zhang", "dev123")
    check("张工登录成功", bool(utok))

    r = httpx.get(f"{IAM}/iam/agents",
                  headers={"Authorization": f"Bearer {utok}"}, timeout=5)
    check("查看自己的 Agent 列表", r.status_code == 200)
    if r.status_code == 200:
        agents = r.json().get("agents", [])
        print(f"    张工有 {len(agents)} 个 Agent:")
        for a in agents:
            print(f"      🤖 {a['agent_name']} ({a['agent_type']}) - {a['status']}")

    # ── 场景 5：SOC 运维发现未注册 Agent ──
    print(info)
    print("  📋 场景5: SOC 安全运维 Agent 发现")
    print("    周运维登录 → Agent 发现扫描")
    print("-"*65)

    otok = login_employee("ops_zhou", "ops123")
    check("周运维登录成功", bool(otok))

    r = httpx.get(f"{IAM}/iam/agents/discovery/all",
                  headers={"Authorization": f"Bearer {otok}"}, timeout=5)
    check("Agent 全景查看", r.status_code == 200)
    if r.status_code == 200:
        d = r.json()
        print(f"    总 Agent: {d['total']} | 活跃: {d['active']} | 吊销: {d['revoked']} | 未注册: {d['unregistered']}")

    r = httpx.get(f"{IAM}/iam/agents/discovery/scan",
                  headers={"Authorization": f"Bearer {otok}"}, timeout=5)
    check("Agent 发现扫描", r.status_code == 200)
    if r.status_code == 200:
        sc = r.json()
        print(f"    扫描时间: {sc['scan_time']}")
        print(f"    检测到未注册: {sc['unregistered']} 个")
        for a in sc["unregistered_list"]:
            print(f"      🚨 {a['agent_name']} ({a['agent_type']})")
        print(f"    建议: {sc['recommendation']}")

    # ── 场景 6：吊销异常 Agent ──
    print(info)
    print("  📋 场景6: 吊销异常 Agent")
    print("    张工吊销自己的某个 Agent")
    print("-"*65)

    r = httpx.post(f"{IAM}/iam/agents/2/revoke",  # id=2 是王总的决策分析，张工无权吊销
                   headers={"Authorization": f"Bearer {utok}"}, timeout=5)
    check("张工无权吊销别人的 Agent", r.status_code == 403)

    # 张工用自己的 Agent 测试吊销
    r = httpx.post(f"{IAM}/iam/agents/5/revoke",  # id=5 是张工的数据分析助手
                   headers={"Authorization": f"Bearer {utok}"}, timeout=5)
    check("张工吊销自己的 Agent 成功", r.status_code == 200)
    if r.status_code == 200:
        print(f"    状态: {r.json()['status']}")

    # 验证吊销后不能再用
    tok5 = get_agent_token("dev_zhang")  # agent_id=5 是张工的数据分析助手
    # 重新拿 token（如果已吊销会返回403）
    r = httpx.post(f"{IAM}/iam/agents/5/token",
                   json={"client_id": "agent_zhang_data", "client_secret": "sec_zhang_data456"},
                   timeout=5)
    check("已吊销 Agent 令牌签发被拒", r.status_code == 403)

    # ── 场景 7：王总注册新 Agent（在 Portal 界面操作）──
    print(info)
    print("  📋 场景7: 注册新 Agent + 权限范围限制")
    print("    王总注册 Agent → 权限只能 ≤ admin 权限")
    print("-"*65)

    wtok = login_employee("admin_wang", "admin123")
    check("王总登录成功", bool(wtok))

    # 尝试给 Agent 超出权限的配置（应该被拒绝）
    r = httpx.post(f"{IAM}/iam/agents/register",
                   headers={"Authorization": f"Bearer {wtok}"},
                   json={"agent_name": "越权测试Agent", "agent_type": "generic",
                         "allowed_perms": ["super:admin"]}, timeout=5)
    check("超出权限被拒绝", r.status_code == 400)

    # 注册权限合理的 Agent
    result = register_new_agent(wtok, "智能合同审查", "oa",
                                 ["emp:read", "order:read", "project:read"])
    check(f"注册新Agent成功: {result.get('agent_name','')}", "client_id" in result)
    if "client_id" in result:
        print(f"    client_id: {result['client_id']}")
        print(f"    client_secret: {result['client_secret']} (仅此一次)")
        print(f"    权限: {result['allowed_perms']}")

    # ── 汇总 ──
    print("\n" + "="*65)
    total = passed + failed
    print(f"  演练完成: ✅ {passed}/{total} 通过  ❌ {failed}/{total} 失败")
    print("="*65)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
