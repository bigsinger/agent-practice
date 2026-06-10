# Token Sidecar Demo v4

企业级云原生 Sidecar + IAM + Vault + Web 门户 + 安全运维中心（SOC）。

## 整体架构

```
┌─────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Browser │───▶│  IAM 门户 (:27000)│    │  Portal (:26000)  │
│ 登录页   │    │  · 登录/会话      │    │  · 仪表盘/SOC页  │
└─────────┘    │  · 12人组织+6角色  │    │  · 员工/订单/项目 │
               └────────┬─────────┘    └────────┬─────────┘
                        │ 会话 JWT              │ 会话 JWT
                        ▼                       ▼
               ┌─────────────────────────────────────┐
               │  Sidecar (:29000) · 透明拦截+令牌注入 │
               │  1.验证用户会话(IAM)                  │
               │  2.Workload认证(Vault)               │
               │  3.更换为服务JWT → 转发               │
               └────────┬────────────┬───────────────┘
                        │            │
               ┌────────▼──┐  ┌─────▼────────┐
               │ API-A     │  │ API-B        │
               │ (:28100)  │  │ (:28200)     │
               │ 用户服务   │  │ 业务服务     │
               └───────────┘  └──────────────┘
               ┌──────────────────────────────────────┐
               │  Vault / 沙箱 (:28001)                │
               │  RSA密钥 · 签发 · 吊销 · 审计 · 轮换  │
               └──────────────────────────────────────┘
               ┌──────────────────────────────────────┐
               │  SQLite (starcloud.db)                │
               │  12员工 · 8订单 · 6项目 · 15安全日志   │
               └──────────────────────────────────────┘
```

## 12 人组织（星辰科技）

| 用户 | 姓名 | 部门 | 角色 | 等级 | 密码 |
|------|------|------|------|------|------|
| admin_wang | 王总 | 管理部 | admin CEO | L5 | admin123 |
| admin_li | 李副总 | 管理部 | admin 副总裁 | L4 | admin456 |
| dev_zhang | 张工 | 研发部 | engineer 高级 | L5 | dev123 |
| dev_liu | 刘工 | 研发部 | engineer | L4 | dev456 |
| dev_chen | 陈工 | 研发部 | engineer | L3 | dev789 |
| dev_zhao | 赵工 | 研发部 | engineer 实习生 | L1 | dev000 |
| fin_wu | 吴会计 | 财务部 | finance 主管 | L5 | fin123 |
| fin_huang | 黄会计 | 财务部 | finance | L3 | fin456 |
| ops_zhou | 周运维 | 运维部 | operator 高级 | L5 | ops123 |
| ops_sun | 孙运维 | 运维部 | operator | L2 | ops456 |
| hr_xu | 许HR | 人事部 | hr 人事主管 | L4 | hr123 |
| prod_ma | 马产品 | 产品部 | product 产品经理 | L4 | prod123 |

## 权限模型

| 权限 \ 角色 | admin | engineer | finance | operator | hr | product |
|-------------|-------|----------|---------|----------|----|---------|
| emp:read | ✅全司 | ✅本部门 | ✅本部门 | ✅本部门 | ✅全司 | ✅本部门 |
| salary:read | ✅全司 | ❌ | ✅全司 | ❌ | ❌ | ❌ |
| order:read | ✅全司 | ✅本部门 | ✅全司 | ❌ | ❌ | ✅本部门 |
| project:read | ✅全司 | ✅全司 | ❌ | ✅本部门 | ❌ | ✅全司 |
| log:read | ✅全司 | ❌ | ❌ | ✅全司 | ❌ | ❌ |
| soc:manage | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |

## 启动

```bash
cd token-sidecar-demo
pip install -r requirements.txt
python run_all.py    # 自动初始化DB + 启动全部6个服务
```

打开浏览器访问：**http://localhost:27000**（登录页）

或门户：**http://localhost:26000/portal/login**

## Web 页面一览

| 页面 | 路径 | 谁可访问 |
|------|------|----------|
| 🔑 IAM 登录页 | http://localhost:27000 | 所有人 |
| 📊 门户登录 | /portal/login | 所有人 |
| 📊 仪表盘 | /portal/dashboard | 登录用户（角色感知） |
| 👥 员工管理 | /portal/employees | admin/hr |
| 📦 订单管理 | /portal/orders | admin/finance |
| 📋 项目管理 | /portal/projects | admin/engineer/product |
| 🛡️ 安全运维中心 | /portal/soc | ops_zhou/admin |

## 安全运维中心（SOC）功能

ops_zhou 登录后进入安全运维中心可查看：

1. **安全概览卡片**：日志总数、高危事件、活跃会话、系统状态
2. **权限管控矩阵**：全角色权限对比
3. **安全审计日志**：15 条记录含暴力破解(🔴)、配置变更(🔴)、密码错误(🟡)等
4. **密钥与令牌状态**：当前签发密钥 kid、已吊销令牌数、今日签发量

## SQLite 数据结构

- `employees` — 12 人（含 level L1-L5 控制数据范围）
- `departments` — 6 部门（含预算）
- `salaries` — 12 人（敏感：薪资+奖金+银行账号+税率）
- `orders` — 8 订单（多部门维度）
- `projects` — 6 项目（含成员/预算/状态）
- `security_logs` — 15 安全日志（事件类型/IP/严重级别）

## 验证结果

```
✅ 200 Login page            (IAM)
✅ 200 Admin dashboard       (admin_wang)
✅ 200 Employees page        (admin_wang)
✅ 200 Orders page           (admin_wang)
✅ 200 Projects page         (admin_wang)
✅ 200 SOC page              (ops_zhou)
✅ 200 Engineer dashboard    (dev_zhang)
✅ 200 Finance dashboard     (fin_wu)
✅ 200 HR dashboard          (hr_xu)
✅ 200 Product dashboard     (prod_ma)
```
