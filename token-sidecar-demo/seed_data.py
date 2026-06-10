"""
seed_data.py — 星辰科技 SQLite 数据库初始化
==============================================
生成 12 人组织、订单、项目、薪资、安全日志、Agent 注册表的测试数据。
"""
import sqlite3, json, os, hashlib

DB = os.path.join(os.path.dirname(__file__), "starcloud.db")

def hash_pwd(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def init():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ── 部门表 ──
    c.execute("""CREATE TABLE departments (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, head TEXT, budget REAL
    )""")
    depts = [
        (1,"管理部","admin_wang",5000000),
        (2,"研发部","dev_zhang",12000000),
        (3,"财务部","fin_wu",3000000),
        (4,"运维部","ops_zhou",4000000),
        (5,"人事部","hr_xu",2000000),
        (6,"产品部","prod_ma",3500000),
    ]
    c.executemany("INSERT INTO departments VALUES(?,?,?,?)", depts)

    # ── 员工表（12人） ──
    c.execute("""CREATE TABLE employees (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT,
        dept TEXT, role TEXT, title TEXT, level INTEGER, phone TEXT,
        password_hash TEXT, last_login TEXT
    )""")
    employees = [
        (1,"admin_wang","王总","wang@starcloud.com","管理部","admin","CEO",5,"13800001001",hash_pwd("admin123"),None),
        (2,"admin_li","李副总","li@starcloud.com","管理部","admin","副总裁",4,"13800001002",hash_pwd("admin456"),None),
        (3,"dev_zhang","张工","zhang@starcloud.com","研发部","engineer","高级工程师",5,"13800001003",hash_pwd("dev123"),None),
        (4,"dev_liu","刘工","liu@starcloud.com","研发部","engineer","工程师",4,"13800001004",hash_pwd("dev456"),None),
        (5,"dev_chen","陈工","chen@starcloud.com","研发部","engineer","工程师",3,"13800001005",hash_pwd("dev789"),None),
        (6,"dev_zhao","赵工","zhao@starcloud.com","研发部","engineer","实习生",1,"13800001006",hash_pwd("dev000"),None),
        (7,"fin_wu","吴会计","wu@starcloud.com","财务部","finance","财务主管",5,"13800001007",hash_pwd("fin123"),None),
        (8,"fin_huang","黄会计","huang@starcloud.com","财务部","finance","会计",3,"13800001008",hash_pwd("fin456"),None),
        (9,"ops_zhou","周运维","zhou@starcloud.com","运维部","operator","高级运维工程师",5,"13800001009",hash_pwd("ops123"),None),
        (10,"ops_sun","孙运维","sun@starcloud.com","运维部","operator","运维工程师",2,"13800001010",hash_pwd("ops456"),None),
        (11,"hr_xu","许HR","xu@starcloud.com","人事部","hr","人事主管",4,"13800001011",hash_pwd("hr123"),None),
        (12,"prod_ma","马产品","ma@starcloud.com","产品部","product","产品经理",4,"13800001012",hash_pwd("prod123"),None),
    ]
    c.executemany("INSERT INTO employees VALUES(?,?,?,?,?,?,?,?,?,?,?)", employees)

    # ── 薪资表（敏感数据） ──
    c.execute("""CREATE TABLE salaries (
        employee_id INTEGER PRIMARY KEY, base_salary REAL, bonus REAL,
        bank_account TEXT, tax_rate REAL
    )""")
    salaries = [
        (1,180000,360000,"6222****0101",0.45),
        (2,120000,240000,"6222****0102",0.35),
        (3,65000,130000,"6222****0103",0.25),
        (4,45000,80000,"6222****0104",0.20),
        (5,35000,60000,"6222****0105",0.15),
        (6,8000,5000,"6222****0106",0.05),
        (7,50000,100000,"6222****0107",0.20),
        (8,25000,40000,"6222****0108",0.10),
        (9,55000,110000,"6222****0109",0.20),
        (10,18000,25000,"6222****0110",0.08),
        (11,40000,70000,"6222****0111",0.15),
        (12,50000,90000,"6222****0112",0.20),
    ]
    c.executemany("INSERT INTO salaries VALUES(?,?,?,?,?)", salaries)

    # ── 订单表 ──
    c.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY, order_no TEXT UNIQUE, customer TEXT,
        amount REAL, status TEXT, dept TEXT, created_by TEXT, created_at TEXT
    )""")
    orders = [
        (1,"ORD-20260601-001","张三",299.00,"paid","管理部","admin_wang","2026-06-01 09:30:00"),
        (2,"ORD-20260601-002","李四",1599.50,"shipped","研发部","dev_zhang","2026-06-01 10:15:00"),
        (3,"ORD-20260602-003","王五",89.90,"pending","财务部","fin_wu","2026-06-02 14:00:00"),
        (4,"ORD-20260603-001","赵六",4599.00,"paid","管理部","admin_li","2026-06-03 08:45:00"),
        (5,"ORD-20260604-002","孙七",12000.00,"shipped","研发部","dev_liu","2026-06-04 11:20:00"),
        (6,"ORD-20260605-003","周八",350.00,"pending","运维部","ops_zhou","2026-06-05 16:30:00"),
        (7,"ORD-20260606-001","吴九",8800.00,"paid","产品部","prod_ma","2026-06-06 09:00:00"),
        (8,"ORD-20260607-002","郑十",25600.00,"shipped","管理部","admin_wang","2026-06-07 13:45:00"),
    ]
    c.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)", orders)

    # ── 项目表 ──
    c.execute("""CREATE TABLE projects (
        id INTEGER PRIMARY KEY, name TEXT, lead TEXT, members TEXT,
        budget REAL, status TEXT, deadline TEXT, dept TEXT
    )""")
    projects = [
        (1,"AI Agent Platform","dev_zhang",json.dumps(["dev_liu","dev_chen","prod_ma"]),300000,"active","2026-09-30","研发部"),
        (2,"IAM 统一认证","dev_liu",json.dumps(["dev_chen","dev_zhao"]),150000,"active","2026-08-15","研发部"),
        (3,"数据中台 v3","dev_zhang",json.dumps(["dev_liu","prod_ma"]),500000,"planning","2027-01-01","研发部"),
        (4,"财务系统升级","fin_wu",json.dumps(["fin_huang","dev_chen"]),200000,"active","2026-10-01","财务部"),
        (5,"运维监控平台","ops_zhou",json.dumps(["ops_sun","dev_liu"]),180000,"active","2026-07-01","运维部"),
        (6,"官网重构","prod_ma",json.dumps(["dev_zhao"]),80000,"pending","2026-11-01","产品部"),
    ]
    c.executemany("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?)", projects)

    # ── 安全审计日志 ──
    c.execute("""CREATE TABLE security_logs (
        id INTEGER PRIMARY KEY, ts TEXT, event_type TEXT, user TEXT,
        ip TEXT, detail TEXT, severity TEXT
    )""")
    logs = [
        (1,"2026-06-10 08:00:00","login","admin_wang","10.0.0.1","CEO 登录系统","info"),
        (2,"2026-06-10 08:05:00","token.issue","sidecar-prod-01","10.0.0.100","为 api-a 签发令牌 aud=api-a","info"),
        (3,"2026-06-10 08:10:00","login","dev_zhang","10.0.0.23","张工登录系统","info"),
        (4,"2026-06-10 08:15:00","api.access","dev_zhang","10.0.0.23","GET /api-a/protected-data 200 OK","info"),
        (5,"2026-06-10 08:20:00","login.failed","unknown","192.168.1.100","密码错误尝试 3次","warning"),
        (6,"2026-06-10 08:30:00","token.revoke","ops_zhou","10.0.0.5","管理员手动吊销异常令牌 jti=abc123","warning"),
        (7,"2026-06-10 08:35:00","key.rotate","ops_zhou","10.0.0.5","触发密钥轮换 kid=key-xxx→key-yyy","info"),
        (8,"2026-06-10 08:40:00","api.access","fin_wu","10.0.0.30","GET /api-b/protected-data 403 权限不足","warning"),
        (9,"2026-06-10 08:45:00","bruteforce","10.0.0.200","10.0.0.200","SSH 爆破攻击 150次/分钟","critical"),
        (10,"2026-06-10 08:50:00","login","ops_zhou","10.0.0.5","运维工程师登录","info"),
        (11,"2026-06-10 08:55:00","system","system","-","数据库自动备份完成","info"),
        (12,"2026-06-10 09:00:00","token.issue","sidecar-prod-02","10.0.0.101","为 api-b 签发令牌 aud=api-b","info"),
        (13,"2026-06-10 09:05:00","login.failed","dev_zhao","10.0.0.24","密码连续错误 5次（锁定时）","warning"),
        (14,"2026-06-10 09:10:00","config.change","ops_zhou","10.0.0.5","修改防火墙规则：开放 8443 端口","critical"),
        (15,"2026-06-10 09:15:00","login","hr_xu","10.0.0.40","许HR登录系统","info"),
    ]
    c.executemany("INSERT INTO security_logs VALUES(?,?,?,?,?,?,?)", logs)

    # ====================================================================
    # Agent IAM — Agent 注册表
    # ====================================================================
    c.execute("""CREATE TABLE agents (
        id INTEGER PRIMARY KEY,
        agent_name TEXT NOT NULL,
        agent_type TEXT DEFAULT 'generic',
        client_id TEXT UNIQUE NOT NULL,
        client_secret_hash TEXT NOT NULL,
        owner_username TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        allowed_perms TEXT,           -- JSON array of "perm" strings
        created_at TEXT,
        last_seen TEXT
    )""")

    # ROLES 定义（与 iam.py 保持一致）
    ROLES = {
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

    def full_perms(role: str) -> list:
        """获取某角色的全量权限列表"""
        return [k for k, v in ROLES[role].items() if v > 0]

    def make_agent(aid, name, atype, owner, cid, pwd, status, perms):
        return (aid, name, atype, cid, hash_pwd(pwd), owner, status,
                json.dumps(perms), "2026-06-10 00:00:00", None)

    agents = [
        # ── 王总 (admin) — 2 agent ──
        make_agent(1,"智能审批助手","oa","admin_wang","agent_wang_oa","sec_wang_oa123","active",
                   full_perms("admin")),  # 全量权限
        make_agent(2,"决策分析顾问","bi","admin_wang","agent_wang_bi","sec_wang_bi456","active",
                   ["emp:read","order:read","project:read","salary:read"]),  # 仅查询类
        # ── 李副总 (admin) — 1 agent ──
        make_agent(3,"运营报告生成","report","admin_li","agent_li_rpt","sec_li_rpt789","active",
                   ["emp:read","order:read","project:read","order:manage"]),
        # ── 张工 (engineer) — 2 agent ──
        make_agent(4,"代码审查助手","code","dev_zhang","agent_zhang_code","sec_zhang_code123","active",
                   full_perms("engineer")),  # 工程全量
        make_agent(5,"数据分析助手","data","dev_zhang","agent_zhang_data","sec_zhang_data456","active",
                   ["project:read","order:read","emp:read"]),  # 只读查询
        # ── 刘工 (engineer) — 1 agent ──
        make_agent(6,"文档智能助手","doc","dev_liu","agent_liu_doc","sec_liu_doc789","active",
                   ["project:read","emp:read"]),
        # ── 陈工 (engineer) — 1 agent ──
        make_agent(7,"测试自动化","qa","dev_chen","agent_chen_qa","sec_chen_qa123","active",
                   ["project:read"]),  # 仅可看项目
        # ── 赵工 (engineer, intern) — 1 agent ──
        make_agent(8,"学习助手","edu","dev_zhao","agent_zhao_edu","sec_zhao_edu456","active",
                   ["project:read"]),  # 实习生只有 project:read
        # ── 吴会计 (finance) — 2 agent ──
        make_agent(9,"账务处理机器人","finance","fin_wu","agent_wu_acct","sec_wu_acct789","active",
                   full_perms("finance")),  # 财务全量
        make_agent(10,"订单分析助手","bi","fin_wu","agent_wu_order","sec_wu_order123","active",
                    ["order:read","order:manage"]),  # 仅订单
        # ── 黄会计 (finance) — 1 agent ──
        make_agent(11,"报销审核助手","finance","fin_huang","agent_huang_exp","sec_huang_exp456","active",
                    ["order:read"]),  # 仅可看订单
        # ── 周运维 (operator) — 2 agent ──
        make_agent(12,"安全巡检机器人","secops","ops_zhou","agent_zhou_sec","sec_zhou_sec789","active",
                    full_perms("operator")),  # 运维全量
        make_agent(13,"告警通知推送","alert","ops_zhou","agent_zhou_alert","sec_zhou_alert123","active",
                    ["log:read","soc:manage"]),  # 仅日志+安全
        # ── 孙运维 (operator) — 1 agent ──
        make_agent(14,"日志采集Agent","log","ops_sun","agent_sun_log","sec_sun_log456","active",
                    ["log:read"]),  # 仅可读日志
        # ── 许HR (hr) — 1 agent ──
        make_agent(15,"简历筛选助手","hr","hr_xu","agent_xu_resume","sec_xu_resume789","active",
                    full_perms("hr")),  # 人事全量
        # ── 马产品 (product) — 1 agent ──
        make_agent(16,"需求管理助手","product","prod_ma","agent_ma_req","sec_ma_req123","active",
                    ["project:read","order:read"]),  # 仅查询

        # ── 🚨 未授权 Agent（模拟违规发现）──
        make_agent(17,"幽灵爬虫-7788","unknown","unknown","ghost_crawler","no_auth_xxx","pending",
                    []),  # 未注册，状态 pending
    ]

    c.executemany("""INSERT INTO agents VALUES(?,?,?,?,?,?,?,?,?,?)""", agents)

    conn.commit(); conn.close()
    print(f"✅ 数据库已初始化: {DB}")
    print(f"   部门: {len(depts)} | 员工: {len(employees)} | 订单: {len(orders)}")
    print(f"   项目: {len(projects)} | 薪资: {len(salaries)} | 安全日志: {len(logs)}")
    print(f"   Agent: {len(agents)-1} 已注册 + 1 未授权（共{len(agents)}）")

if __name__ == "__main__":
    init()
