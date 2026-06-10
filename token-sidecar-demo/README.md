# Token Sidecar Demo v3

企业级云原生 Sidecar 透明拦截模式——包含完整 IAM 身份认证、Token Vault、密钥轮换、审计日志。

## 核心回答

**① 沙箱是干嘛的？**
沙箱是**独立部署的密钥管理服务（Vault/KMS）**，不是请求者运行的环境。它是整个体系的**信任根**：
- 持有 RSA 私钥（生产存 HSM）
- 验证 Sidecar 的 Workload Identity → 签发限域令牌
- 审计日志全记录、密钥轮换、令牌吊销

**② 请求者跑在哪？**
请求者（应用/用户）跑在**业务 Pod 中**，和 Sidecar 容器同 Pod。在 K8s 中：
- Pod 包含 1 个业务容器 + 1 个 Sidecar 容器
- iptables 透明拦截所有流量到 Sidecar
- 请求者完全不知 Sidecar 和 Vault 的存在

**③ iptables 怎么拦截？**
K8s Pod 启动时 initContainer 执行：
```bash
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 15006
```
将所有目标端口 80 的流量重定向到 Sidecar（15006）。本 demo 因在 Windows 运行，用**反向代理**模拟此效果。

## v3 架构

```
                    ┌──────────────────┐
                    │  星辰科技 · 10人   │
                    │  Admin/Eng/Fin/Ops│
                    └────────┬─────────┘
                             │ 登录 username/password
                             ▼
                    ┌──────────────────┐  ┌──────────────────┐
                    │  IAM (:27000)    │  │  沙箱 (:28001)    │
                    │  · 身份认证       │  │  · 私钥管理(RSA)  │
                    │  · RBAC 权限     │  │  · Workload 认证  │
                    │  · 会话签发       │  │  · 密钥轮换       │
                    └────────┬─────────┘  │  · 令牌吊销       │
                             │ 会话 JWT   │  · 审计日志       │
                             ▼            └────────┬─────────┘
┌─────────┐    ┌──────────────────┐                │
│ 请求者   │───▶│  Sidecar (:29000)│◀──Workload────┘
│ (用户)   │    │  · 验证会话(IAM)  │   Identity
│          │    │  · 取令牌(Vault)  │
│          │    │  · 注入/置换      │────▶ API-A (:28100)
│          │    │  · 缓存/续期      │────▶ API-B (:28200)
└─────────┘    └──────────────────┘
```

## 10 人组织（星辰科技）

| 用户 | 姓名 | 部门 | 角色 | 密码 |
|------|------|------|------|------|
| admin_wang | 王总 | 管理部 | admin | admin123 |
| admin_li | 李副总 | 管理部 | admin | admin456 |
| dev_zhang | 张工 | 研发部 | engineer | dev123 |
| dev_liu | 刘工 | 研发部 | engineer | dev456 |
| dev_chen | 陈工 | 研发部 | engineer | dev789 |
| dev_zhao | 赵工 | 研发部 | engineer | dev000 |
| fin_wu | 吴会计 | 财务部 | finance | fin123 |
| fin_huang | 黄会计 | 财务部 | finance | fin456 |
| ops_zhou | 周运维 | 运维部 | operator | ops123 |
| ops_sun | 孙运维 | 运维部 | operator | ops456 |

## 组件

| 组件 | 端口 | 职责 |
|------|------|------|
| IAM | 27000 | 用户身份认证 + RBAC + 会话管理 |
| Vault/沙箱 | 28001 | 私钥管理 + 令牌签发/吊销 + 审计 + 密钥轮换 |
| API-A | 28100 | 用户服务（验证 aud=api-a, 返回团队数据） |
| API-B | 28200 | 订单服务（验证 aud=api-b, 返回订单数据） |
| Sidecar | 29000 | 透明代理 + 会话验证 + Workload认证 + 令牌注入 |
| 请求者 | — | 登录IAM → 通过Sidecar访问API |

## 启动

```bash
cd token-sidecar-demo
pip install -r requirements.txt
python run_all.py          # 启动全部 5 个服务
# 另开终端：
python requester.py        # 交互式多用户演示
```

## 完整数据流

```
Step 1: 用户登录
  Requester ──POST /iam/login──▶ IAM (:27000)
  IAM ──{session_token}──▶ Requester

Step 2: 请求通过 Sidecar
  Requester ──GET /api-a/protected-data──▶ Sidecar (:29000)
  Header: Authorization: Bearer {session_token}

Step 3: Sidecar 验证会话
  Sidecar ──GET /iam/verify──▶ IAM
  IAM ──{user_id, role, perms}──▶ Sidecar

Step 4: Sidecar Workload 认证到 Vault
  Sidecar ──POST /vault/auth──▶ Vault (:28001)
  {workload_id: "sidecar-prod-01"}
  Vault ──{vault_token}──▶ Sidecar

Step 5: Sidecar 换取服务 JWT
  Sidecar ──POST /vault/token──▶ Vault
  Authorization: Bearer {vault_token}
  {audience: "api-a", scope: "read:users", user_info}

Step 6: 注入并转发
  Sidecar ──GET /protected-data──▶ API-A (:28100)
  Authorization: Bearer {service_jwt}    ← 已置换
  X-User-Id: dev_zhang
  API-A ──200 {user data}──▶ Sidecar ──▶ Requester

请求者眼中：只做了登录 + 发请求，不知 Vault、不知密钥、不知 Sidecar 拦截。
```

## 运行效果

```
📋 公司组织：星辰科技 (StarCloud Tech)
  admin_wang     王总     管理部    admin       admin123
  dev_zhang      张工     研发部    engineer    dev123
  ...

👤 用户: dev_zhang (高级工程师 — 研发人员)
  ✅ IAM 登录成功 | role: engineer | 部门: 研发部
     权限: api-a:read, api-a:write, api-b:read

  🔄 请求 → http://localhost:29000/api-a/protected-data
  ✅ API-A (User Service) | 200 OK
     请求者: 张工 (engineer)
     团队: 4 人

  🔄 请求 → http://localhost:29000/api-b/protected-data
  ✅ API-B (Order Service) | 200 OK
     请求者: 张工 (engineer)
     订单数: 4

👤 用户: fin_wu (财务主管 — 财务人员)
  ✅ IAM 登录成功 | role: finance | 部门: 财务部

  🔒 权限限制：财务人员访问 API-A → 沙箱只签发 read:orders scope
```

## 沙箱真实能力

| 功能 | 端点 | 生产对标 |
|------|------|----------|
| Workload 认证 | POST /vault/auth | Vault K8s Auth |
| 签发限域 JWT | POST /vault/token | Vault PKI/Token |
| 令牌吊销 | POST /vault/token/revoke | Vault Token Revoke |
| 密钥轮换 | POST /vault/keys/rotate | Vault Key Rotation |
| 审计日志 | GET /vault/audit | Vault Audit Log |
| 密钥列表 | GET /vault/keys | Vault Key Info |

## 生产 vs Demo

| 方面 | Demo | 生产环境 |
|------|------|----------|
| 流量拦截 | 反向代理 | iptables REDIRECT (K8s+Istio) |
| 密钥存储 | 内存 RSA | HSM / KMS |
| IAM 认证 | 简单密码 | OIDC / LDAP / SAML |
| Workload 认证 | 预配置 ID 列表 | K8s Service Account JWT |
| 密钥轮换 | 保留 4 个 key | 带自动过期和 CRL |
| 高可用 | 单实例 | 集群 + Raft 共识 |
