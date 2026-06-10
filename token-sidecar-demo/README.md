# Token Sidecar Demo v2

云原生 Sidecar 透明拦截模式——多 API 场景的令牌置换。

> **回答几个关键问题：**
> - **请求者需要做什么？** 什么都不做。只管发出 HTTP 请求，不管理 token、不知道沙箱、不做认证。
> - **Sidecar 是主动拦截的吗？** 是的。生产环境（K8s+Istio）通过 **iptables** 将 Pod 的所有进出流量透明重定向到 Sidecar 端口 (15006)。本 demo 用反向代理模拟这一过程。
> - **多 API 也一样原理？** 完全一样。Sidecar 维护路由表，按请求路径匹配目标 API，取 **不同 audience + scope** 的 JWT 分别注入，互不干扰。

---

## 真实生产原理

在 Kubernetes + Istio 中：

```
┌─────────────────────────────────┐
│ Pod                             │
│  ┌──────────┐  ┌────────────┐  │
│  │ 业务容器  │──│ Envoy      │  │
│  │ (App)    │  │ Sidecar    │  │
│  │          │  │ (:15006)   │  │
│  └──────────┘  └────────────┘  │
│       ↑               ↑        │
│  iptables 将所有流量    │        │
│  重定向到 sidecar      │        │
└─────────────────────────────────┘
```

- 请求者完全不知 Sidecar 的存在——它只向 API 地址发请求
- `iptables -t nat` 规则将所有进出 Pod 的 TCP 流量重定向到 Sidecar 的 15006 端口
- Sidecar 完成认证、授权、令牌注入后，再将请求转发给业务容器

## 本 Demo 架构

```
请求者（零感知）
  │
  │── GET /api-a/protected-data  (以为在调 API-A)
  │── GET /api-b/protected-data  (以为在调 API-B)
  │
  ▼
Sidecar (:29000)  ← 透明代理
  │
  ├── 匹配 /api-a/* → 向沙箱取 audience=api-a scope=read:users 的 JWT
  │                   注入 Authorization → 转发到 API-A (:28100)
  │
  └── 匹配 /api-b/* → 向沙箱取 audience=api-b scope=read:orders 的 JWT
                      注入 Authorization → 转发到 API-B (:28200)
                              │
                              ▼
                        沙箱 (:28001)
                        Token Vault（RSA-2048 密钥对）
```

## 组件

| 组件 | 端口 | 角色 |
|------|------|------|
| **沙箱** | 28001 | RSA-2048 密钥对，签发不同 audience/scope 的 RS256 JWT |
| **API-A** | 28100 | 用户服务，验证 `audience=api-a` + `scope=read:users` |
| **API-B** | 28200 | 订单服务，验证 `audience=api-b` + `scope=read:orders` |
| **Sidecar** | 29000 | 透明代理，按路径路由 + 自动令牌获取/注入/缓存/续期 |
| **请求者** | — | 零感知，只管发 HTTP 请求 |

## 令牌设计（贴近生产）

| 维度 | API-A 令牌 | API-B 令牌 | 意义 |
|------|-----------|-----------|------|
| **audience** | `api-a` | `api-b` | 令牌只能被目标 API 验证通过 |
| **scope** | `read:users` | `read:orders` | 令牌只能访问对应的数据域 |
| **签名** | RS256 (同一对 RSA 密钥) | RS256 | 沙箱私钥签，API 公钥验 |
| **有效期** | 60 秒 | 60 秒 | 短期令牌，Sidecar 自动续期 |

> API-A 的令牌发给 API-B → 验证失败（audience 不匹配）
> API-B 的令牌发给 API-A → 验证失败（scope 不含 read:users）
> 过期令牌 → 验证失败（Sidecar 自动续期，请求者无感）

## 启动

```bash
cd token-sidecar-demo
pip install -r requirements.txt
python run_all.py          # 启动全部 4 个服务
# 另开终端：
python requester.py        # 发起测试
```

## 真实运行日志（三方完全记录）

### 沙箱 (Sandbox) — `sandbox.log`

```
10:14:51 [SAND] 正在生成 RSA-2048 密钥对...
10:14:51 [SAND] 密钥对就绪 | kid=key-8ea53fb2
INFO:     127.0.0.1:61667 - "GET /public-key HTTP/1.1" 200 OK   ← API-A 拉取公钥
INFO:     127.0.0.1:52881 - "GET /public-key HTTP/1.1" 200 OK   ← API-B 拉取公钥
10:15:15 [SAND] 签发令牌 | aud=api-a | scope=read:users | exp=60s | jti=1a00...
INFO:     127.0.0.1:52906 - "POST /token HTTP/1.1" 200 OK        ← Sidecar 为 API-A 取令牌
10:15:19 [SAND] 签发令牌 | aud=api-b | scope=read:orders | exp=60s | jti=b158...
INFO:     127.0.0.1:52913 - "POST /token HTTP/1.1" 200 OK        ← Sidecar 为 API-B 取令牌
```

### Sidecar — `sidecar.log`

```
10:15:14 [SIDE] 令牌需要刷新 | audience=api-a scope=read:users  ① 冷启动：取 API-A 令牌
10:15:15 [SIDE] HTTP Request: POST http://localhost:28001/token     → 从沙箱获取
10:15:15 [SIDE] 令牌已缓存 | audience=api-a | 有效期=60s
10:15:15 [SIDE] 拦截 → API-A (User Service) | 注入令牌 aud=api-a  ② 注入并转发
10:15:15 [SIDE] 转发 → http://localhost:28100/protected-data
10:15:16 [SIDE] HTTP Request: GET http://localhost:28100/protected-data
10:15:16 [SIDE] 响应 | API-A (User Service) → 200                 ③ 返回成功

10:15:18 [SIDE] 令牌需要刷新 | audience=api-b scope=read:orders  ④ 新路由：取 API-B 令牌
10:15:19 [SIDE] HTTP Request: POST http://localhost:28001/token
10:15:19 [SIDE] 令牌已缓存 | audience=api-b | 有效期=60s
10:15:19 [SIDE] 拦截 → API-B (Order Service) | 注入令牌 aud=api-b  ⑤ 注入并转发
10:15:19 [SIDE] HTTP Request: GET http://localhost:28200/protected-data
10:15:19 [SIDE] 响应 | API-B (Order Service) → 200               ⑥ 返回成功

10:15:21 [SIDE] 拦截 → API-A (User Service) | 注入令牌 aud=api-a  ⑦ 缓存命中（无沙箱交互）
10:15:22 [SIDE] HTTP Request: GET http://localhost:28100/protected-data
10:15:22 [SIDE] 响应 | API-A (User Service) → 200                 ⑧ 直接返回
```

### 业务 API-A（用户服务）— `api-a.log`

```
10:14:55 [API-A] 公钥已就绪 | kid=key-8ea53fb2    ← 启动时从沙箱拉取公钥
10:15:16 [API-A] 令牌验证通过 | sub=sidecar | scope=read:users   ① 第一次请求
10:15:16 [API-A] 返回用户数据 | client=sidecar-prod-01
10:15:22 [API-A] 令牌验证通过 | sub=sidecar | scope=read:users   ② 缓存命中（同一令牌）
10:15:22 [API-A] 返回用户数据 | client=sidecar-prod-01
```

### 业务 API-B（订单服务）— `api-b.log`

```
10:14:56 [API-B] 公钥已就绪 | kid=key-8ea53fb2    ← 启动时从沙箱拉取公钥
10:15:19 [API-B] 令牌验证通过 | sub=sidecar | scope=read:orders   ① 第一次请求
10:15:19 [API-B] 返回订单数据 | client=sidecar-prod-01
```

### 请求者（零感知）— `requester.py` 输出

```
[REQ ] 请求者 → http://localhost:29000/api-a/protected-data
[REQ ]   我的视角：直接调用 API-A (User Service)
[REQ ]   实际路径：请求被 Sidecar 拦截并注入令牌
[REQ ] HTTP Request: GET ... "HTTP/1.1 200 OK"     ← 请求者眼中只是正常 API 调用

  ✅ 返回用户数据: {user_id: "u_10086", name: "张三", level: "premium"}
      令牌信息: {audience: "api-a", scope: "read:users", issuer: "sandbox-vault"}

[REQ ] 请求者 → http://localhost:29000/api-b/protected-data
[REQ ] HTTP Request: GET ... "HTTP/1.1 200 OK"

  ✅ 返回订单数据: 3 条订单（ORD-20260601-001 等）
      令牌信息: {audience: "api-b", scope: "read:orders", issuer: "sandbox-vault"}

[REQ ] 请求者 → http://localhost:29000/api-a/protected-data（二次请求）
[REQ ] HTTP Request: GET ... "HTTP/1.1 200 OK"

  ✅ 缓存命中（同 expires_at，无沙箱交互）
```

## 完整时序

```
请求者                  Sidecar                  沙箱                    API-A / API-B
  │                       │                       │                        │
  │── GET /api-a/... ────▶│                       │                        │
  │                       │── POST /token ───────▶│                        │
  │                       │◀── JWT (aud=api-a) ───│                        │
  │                       │                       │                        │
  │                       │── GET /protected ─────│───────────────────────▶│ (注入 JWT)
  │                       │                       │                        │── 验证 aud=api-a
  │                       │                       │                        │── 验证 scope=read:users
  │◀──────── 200 OK ─────│◀───────────────────────────────────────────────│
  │                       │                       │                        │
  │── GET /api-b/... ────▶│                       │                        │
  │                       │── POST /token ───────▶│                        │
  │                       │◀── JWT (aud=api-b) ───│                        │
  │                       │                       │                        │
  │                       │── GET /protected ─────│───────────────────────▶│ API-B
  │◀──────── 200 OK ─────│◀───────────────────────────────────────────────│
```

## 关键结论

1. **请求者零改动** — 不管理 token，不知道沙箱，不关心认证
2. **Sidecar 透明拦截** — 生产用 `iptables -t nat` 透明重定向；本 demo 用反向代理模拟
3. **多 API 自动区分** — 按路径匹配，取不同 audience/scope 的 JWT，互不干扰
4. **令牌隔离** — API-A 的 token 对 API-B 无效（audience + scope 双层隔离）
5. **自动续期** — 过期前 10s 预刷新，请求者全程无感

## 生产 vs Demo 差异

| 方面 | Demo | 生产环境 |
|------|------|----------|
| 流量拦截 | 明确的反向代理 | iptables 透明重定向（K8s + Istio） |
| 身份认证 | 无认证即可调 `/token` | mTLS / Workload Identity / SPIFFE SVID |
| 密钥存储 | 内存生成 RSA 密钥对 | HSM / KMS / Vault Seal |
| 令牌缓存 | 进程内字典 | 共享内存 / Redis / Unix Domain Socket |
| 高可用 | 单实例 | 多副本 + 分布式锁 |
