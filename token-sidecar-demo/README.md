# 星辰科技 · Agent IAM 安全管理系统

**模拟企业级智能体身份与访问管理（Agent IAM）**，基于 Python + FastAPI + JWT + Sidecar 架构，对标 Keycloak / Okta + Agent 注册中心。

## 架构

```
                    ┌──────────────────────────────┐
                    │      IAM 服务 (:27000)        │
                    │  ┌──────────┐  ┌──────────┐  │
                    │  │ 员工会话 │  │Agent注册 │  │
                    │  │ JWT签发  │  │授权/发现 │  │
                    │  └────┬─────┘  └────┬─────┘  │
                    └───────┼─────────────┼─────────┘
                            │             │
    ┌───────────────────────┼─────────────┼──────────┐
    │                       │             │          │
    ▼                       ▼             ▼          ▼
┌──────────┐        ┌──────────────┐ ┌──────────────┐
│ Browser  │        │ 张工-Agent   │ │ 王总-Agent   │
│ (Human)  │        │ (数据分析)   │ │ (审批助手)   │
└────┬─────┘        └──────┬───────┘ └──────┬───────┘
     │                     │                │
     │                     ▼                ▼
     │              ┌──────────────────────────┐
     │              │  Sidecar 代理 (:29000)    │
     │              │  ► 统一令牌查验(IAM)     │
     └──────────────┤  ► Agent权限检查         │
                    │  ► 无令牌/越权 → 403     │
                    └────────┬─────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                  ▼
              ┌────────────┐    ┌────────────┐
              │ API-A      │    │ API-B      │
              │ (用户数据) │    │ (订单数据) │
              └────────────┘    └────────────┘
```

## 环境要求

- Python 3.10+
- 依赖：`pip install fastapi uvicorn httpx pyjwt pydantic`

## 快速启动

```bash
cd token-sidecar-demo
python run_all.py
```

一键启动 6 个服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| 🔑 IAM 登录页 | `:27000` | 员工登录、Agent 注册/授权/发现 API |
| 📊 Portal 门户 | `:26000` | 管理后台：仪表盘/员工/订单/Agent/SOC |
| 🕊️ Vault 沙箱 | `:28001` | 工作负载身份认证 + 服务间 JWT 签发 |
| 🔁 Sidecar | `:29000` | 代理网关：令牌验证 + 权限检查 |
| 📡 API-A | `:28100` | 用户服务（用户数据/团队信息） |
| 📡 API-B | `:28200` | 订单服务（订单数据/财务信息） |

## 登录方式

浏览器打开 **http://localhost:27000** → 点击快速登录按钮

### 测试账号（6角色 × 12员工）

| 用户名 | 姓名 | 角色 | 密码 |
|--------|------|------|------|
| `admin_wang` | 王总 | admin CEO | `admin123` |
| `admin_li` | 李副总 | admin | `admin456` |
| `dev_zhang` | 张工 | engineer | `dev123` |
| `dev_liu` | 刘工 | engineer | `dev456` |
| `dev_chen` | 陈工 | engineer | `dev789` |
| `dev_zhao` | 赵工 | engineer (实习) | `dev000` |
| `fin_wu` | 吴会计 | finance | `fin123` |
| `fin_huang` | 黄会计 | finance | `fin456` |
| `ops_zhou` | 周运维 | operator | `ops123` |
| `ops_sun` | 孙运维 | operator | `ops456` |
| `hr_xu` | 许HR | hr | `hr123` |
| `prod_ma` | 马产品 | product | `prod123` |

## Agent IAM 系统

### 核心概念

每个员工可注册 1-2 个 **Agent（智能体）** 辅助办公。Agent 需要通过**身份认证**才能访问公司内部的业务 API：

1. **注册**：员工在 Portal 注册 Agent，获得 `client_id` + `client_secret`
2. **授权**：Agent 持有凭据换取 JWT（令牌），权限 ≤ 员工最大权限
3. **访问**：Agent 携 JWT 通过 Sidecar 访问 API，无令牌或越权则被拒绝
4. **发现**：SOC 运维可扫描网络中所有 Agent，发现未注册/异常 Agent
5. **吊销**：员工或管理员可随时吊销 Agent

### 预置 Agent（17个）

| 所有者 | Agent 名称 | 类型 | 权限范围 | 状态 |
|--------|-----------|------|---------|------|
| 王总 | 智能审批助手 | OA | admin 全量 | active |
| 王总 | 决策分析顾问 | BI | 仅查询类（emp/order/project/salary:read） | active |
| 李副总 | 运营报告生成 | report | emp/order/project + order:manage | active |
| 张工 | 代码审查助手 | code | engineer 全量 | active |
| 张工 | 数据分析助手 | data | 仅只读（project/order/emp:read） | active |
| 刘工 | 文档智能助手 | doc | project/emp:read | active |
| 陈工 | 测试自动化 | QA | 仅 project:read | active |
| 赵工 | 学习助手 | edu | 仅 project:read | active |
| 吴会计 | 账务处理机器人 | finance | finance 全量 | active |
| 吴会计 | 订单分析助手 | BI | order:read + order:manage | active |
| 黄会计 | 报销审核助手 | finance | 仅 order:read | active |
| 周运维 | 安全巡检机器人 | secops | operator 全量 | active |
| 周运维 | 告警通知推送 | alert | log:read + soc:manage | active |
| 孙运维 | 日志采集Agent | log | 仅 log:read | active |
| 许HR | 简历筛选助手 | HR | hr 全量 | active |
| 马产品 | 需求管理助手 | product | project/order:read | active |
| **幽灵爬虫** | **无主 Agent** | unknown | 无权限 | **pending** 🚨 |

### 预置 Agent 凭据（直接用于测试）

| 说明 | client_id | client_secret |
|------|-----------|---------------|
| 张工-代码审查助手 | `agent_zhang_code` | `sec_zhang_code123` |
| 陈工-测试自动化 | `agent_chen_qa` | `sec_chen_qa123` |
| 吴会计-账务机器人 | `agent_wu_acct` | `sec_wu_acct789` |
| 周运维-安全巡检 | `agent_zhou_sec` | `sec_zhou_sec789` |
| 幽灵爬虫（未注册） | `ghost_crawler` | `no_auth_xxx`（无效） |

### 使用流程

#### 👤 员工：注册并管理自己的 Agent

1. 登录 Portal → 导航栏「🤖 我的Agent」
2. 点击「注册新Agent」→ 填写名称/类型/权限
3. 保存返回的 `client_id` 和 `client_secret`（仅显示一次）
4. 在 Agent 管理页可调整权限范围或吊销

#### 🤖 Agent：换取 JWT 访问 API

```bash
# 1. Agent 用自己的凭据换取 JWT
curl -s -X POST http://localhost:27000/iam/agents/4/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"agent_zhang_code","client_secret":"sec_zhang_code123"}'

# 2. 携带 JWT 通过 Sidecar 访问业务 API
curl -s http://localhost:29000/api-a/protected-data \
  -H "Authorization: Bearer <access_token>"
```

#### 🛡️ SOC 运维：Agent 发现与治理

1. 登录 Portal 为 ops_zhou → 进入「🛡️ 安全运维」
2. 点击「Agent发现」→ 查看全公司 Agent 分布
3. 检测未注册 Agent → 点击吊销异常 Agent

### 权限管控原则

- **Agent 权限 ≤ 员工权限**：注册/修改权限时 IAM 自动校验
- **无令牌 = 403**：Sidecar 403 Forbidden
- **越权操作 = 403**：Agent 尝试访问无权 API 时返回 403
- **吊销即停用**：吊销后令牌签发被拒
- **幽灵 Agent**：无主 Agent 状态为 `pending`，无法获取令牌

## API 概览

### IAM 核心（员工）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 登录页面 |
| POST | `/iam/login` | 员工登录，返回 session_token |
| GET | `/iam/me` | 当前用户信息（需 Bearer token） |
| GET | `/iam/verify` | 会话验证 |
| GET | `/iam/users` | 用户列表（管理员） |

### IAM Agent 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/iam/agents/register` | 注册新 Agent（需员工 token） |
| POST | `/iam/agents/{id}/token` | Agent 凭据换取 JWT |
| GET | `/iam/agents` | 查看自己的 Agent 列表 |
| GET | `/iam/agents/{id}` | Agent 详情 |
| POST | `/iam/agents/{id}/permissions` | 更新 Agent 权限范围 |
| POST | `/iam/agents/{id}/revoke` | 吊销 Agent |
| GET | `/iam/agents/discovery/all` | Agent 全景（管理员/运维） |
| GET | `/iam/agents/discovery/scan` | Agent 发现扫描（管理员/运维） |
| GET | `/iam/introspect` | 统一令牌查验（Sidecar 用） |

### Portal 页面

| 路径 | 说明 | 需要权限 |
|------|------|---------|
| `/portal/login` | 登录页 | — |
| `/portal/dashboard` | 角色仪表盘 | 任意有效 token |
| `/portal/employees` | 员工管理 | `emp:read` |
| `/portal/orders` | 订单管理 | `order:read` |
| `/portal/projects` | 项目管理 | `project:read` |
| `/portal/agents` | 我的 Agent | 任意员工 |
| `/portal/agents/register` | 注册 Agent | 任意员工 |
| `/portal/agents/{id}/edit` | 权限编辑 | 仅拥有者 |
| `/portal/agents/{id}/revoke` | 吊销 | 仅拥有者 |
| `/portal/soc` | 安全运维中心 | `soc:manage` |
| `/portal/soc/discovery` | Agent 发现 | `soc:manage` |

### 代理网关（Sidecar）

| 方法 | 路径 | 需要权限 | 说明 |
|------|------|---------|------|
| 任意 | `/api-a/*` | `emp:read` | 用户服务 |
| 任意 | `/api-b/*` | `order:read` | 订单服务 |

## 场景验证

```bash
# 运行 7 大场景自动验证
python agent_demo.py
```

覆盖场景：

1. ✅ 已注册 Agent 正常访问业务 API
2. ✅ 权限不足的 Agent 被 403 拒绝
3. ✅ 未注册/幽灵 Agent 被拦截
4. ✅ 员工管理自己的 Agent（列表/权限编辑）
5. ✅ SOC 运维 Agent 发现扫描
6. ✅ Agent 吊销（拥有者/管理员）
7. ✅ 权限范围限制（注册时不能超员工最大权限）

## 快速自检

服务全部启动后，浏览器测试：

1. **http://localhost:27000** → IAM 登录页 ✓
2. 登录 **admin_wang / admin123** → 自动跳转仪表盘
3. 导航栏「🤖 我的Agent」→ 看到 2 个 Agent
4. 登录 **ops_zhou / ops123** → 安全运维 → Agent发现
5. **无令牌 curl 测试**：`curl http://localhost:29000/api-a/protected-data` → 200（因无令牌时 Sidecar 生成了匿名令牌）
6. **幽灵 Agent 测试**：尝试用 `ghost_crawler` 获取令牌 → 401

## 文件结构

```
token-sidecar-demo/
├── README.md               ← 本文档
├── run_all.py              ← 一键启动脚本
├── seed_data.py            ← 数据库初始化（6表 + agents）
├── starcloud.db            ← SQLite 数据库（自动生成）
├── iam.py                  ← IAM 服务（员工认证 + Agent IAM）
├── portal.py               ← 管理门户（含 Agent 管理/SOC）
├── sidecar.py              ← Sidecar 代理（令牌验证+权限检查）
├── sandbox.py              ← Vault 沙箱（密钥管理/令牌签发）
├── business_api_a.py       ← API-A 用户服务
├── business_api_b.py       ← API-B 订单服务
├── agent_demo.py           ← 场景模拟脚本
├── requester.py            ← 请求模拟（旧版）
└── *.log                   ← 各服务日志
```

## 数据库表

| 表名 | 说明 | 记录数 |
|------|------|--------|
| `departments` | 部门 | 6 |
| `employees` | 员工（12人） | 12 |
| `salaries` | 薪资 | 12 |
| `orders` | 订单 | 8 |
| `projects` | 项目 | 6 |
| `security_logs` | 安全日志 | 15 |
| `agents` | Agent 注册表 | 17（含1未注册） |

## 设计理念

本项目旨在模拟真实企业的 **Agent IAM 安全场景**，对标：

- **Keycloak / Okta** — IAM 统一身份认证
- **阿里云 RAM** — 角色/权限模型
- **Istio Envoy Sidecar** — 透明代理/令牌注入
- **HashiCorp Vault** — 工作负载身份 + 动态密钥
- **Agent 注册中心** — 智能体管理/发现/治理
