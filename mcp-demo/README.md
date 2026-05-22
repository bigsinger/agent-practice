# MCP 完整链路演示 Demo

一个最小化的 MCP (Model Context Protocol) 学习与练习项目，演示从 **REST API → MCP 包装 → 安全网关** 的完整调用链路。

---

## 目录

- [项目结构](#项目结构)
- [模块说明](#模块说明)
  - [Module 1 — API Service（模拟后端）](#module-1--api-service模拟后端)
  - [Module 2 — MCP Wrapper（协议包装）](#module-2--mcp-wrapper协议包装)
  - [Module 3 — Security Gateway（安全网关）](#module-3--security-gateway安全网关)
- [快速开始](#快速开始)
- [与 Hermes Agent 集成](#与-hermes-agent-集成)
- [全链路调用流程](#全链路调用流程)
- [实测数据对比](#实测数据对比)
- [扩展练习](#扩展练习)

---

## 项目结构

```
mcp-demo/
├── api_service.py              # Module 1: 模拟 REST API（无外部依赖）
├── mcp_server.py               # Module 2: MCP 协议包装服务
├── mcp_gateway.py              # Module 3: MCP 安全网关（脱敏+日志+检测）
├── run_all.py                  # 一键启动脚本
├── hermes_config.yaml.example  # Hermes Agent 配置示例
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

## 模块说明

### Module 1 — API Service（模拟后端）

**文件**: `api_service.py`

模拟企业内部的 HTTP REST API，使用 Python 标准库 `http.server` 实现（零外部依赖）。

| 端点 | 说明 | 示例 |
|------|------|------|
| `GET /api/users/{id}` | 查询用户（含手机号、邮箱等敏感字段） | `GET /api/users/u001` |
| `GET /api/orders/{id}` | 查询订单详情 | `GET /api/orders/ord001` |
| `GET /api/orders/by-user/{id}` | 查询用户的所有订单 | `GET /api/orders/by-user/u001` |
| `GET /api/weather/{city}` | 天气查询（无敏感信息） | `GET /api/weather/北京` |
| `GET /api/search?q=xxx` | 综合搜索 | `GET /api/search?q=张三` |
| `GET /health` | 健康检查 | — |

**学习要点**：理解 MCP 要包装的"后端资源"长什么样——它们可能是内部服务、数据库、或第三方 API。

---

### Module 2 — MCP Wrapper（协议包装）

**文件**: `mcp_server.py`

将 REST API 包装为 **MCP 工具（Tool）**，使用 `mcp` Python SDK 的 `FastMCP`。

| MCP 工具 | 对应 API | 说明 |
|----------|----------|------|
| `get_user_info(user_id)` | `/api/users/{id}` | 用户查询 |
| `get_order_info(order_id)` | `/api/orders/{id}` | 订单查询 |
| `get_weather(city)` | `/api/weather/{city}` | 天气查询 |
| `search(keyword)` | `/api/search?q=xxx` | 综合搜索 |
| `get_user_orders(user_id)` | `/api/orders/by-user/{id}` | 用户订单列表 |

**学习要点**：
- MCP 不关心后端是 HTTP 服务、数据库还是本地文件——它统一暴露为 Tool
- `FastMCP` 的 `@mcp.tool()` 装饰器自动生成工具 Schema
- 默认使用 `stdio` 传输协议，Hermes Agent 通过子进程标准输入/输出通信

---

### Module 3 — Security Gateway（安全网关）

**文件**: `mcp_gateway.py`

在 MCP 包装器之上添加安全层，演示生产级 MCP 服务需要的安全能力：

| 安全功能 | 实现 | 说明 |
|----------|------|------|
| **Token 认证** | `verify_token()` | 每个工具需传入有效 token，拒绝未授权请求 |
| **访问日志** | `logging` → `gateway_access.log` | 记录每次工具调用的时间、参数、认证状态、响应大小 |
| **数据脱敏** | `mask_sensitive()` | 自动掩码手机号 (`138****8888`)、邮箱前缀、身份证号 |
| **输出检测** | `check_output_safety()` | 扫描返回内容中是否仍有敏感信息泄露 |
| **告警上报** | `logger.warning()` | 认证失败 / 泄露风险时在日志中标记告警 |

每个工具在原始名称后加 `_safe` 后缀以示区分（如 `get_user_info_safe`），且新增 `token` 参数：

| 安全工具 | 对应原始工具 | 差异 |
|----------|-------------|------|
| `get_user_info_safe(token, user_id)` | `get_user_info` | ✅ 认证 + ✅ 脱敏 + ✅ 检测 |
| `get_order_info_safe(token, order_id)` | `get_order_info` | ✅ 认证 + ✅ 脱敏 + ✅ 检测 |
| `get_weather_safe(token, city)` | `get_weather` | ✅ 认证，无敏感信息，仅日志 |
| `search_safe(token, keyword)` | `search` | ✅ 认证 + ✅ 脱敏 + ✅ 检测 |
| `get_user_orders_safe(token, user_id)` | `get_user_orders` | ✅ 认证 + ✅ 脱敏 + ✅ 检测 |

**学习要点**：
- MCP 网关模式：在工具调用前后插入安全处理逻辑
- Token 认证：每个工具函数增加 `token` 参数，调用前验证，拒绝未授权请求
- 脱敏 vs 阻断：脱敏保留数据结构，阻断则返回错误阻止调用
- 安全检测可以是正则、AI 模型、或外部检查服务

---

## 快速开始

### 1. 安装依赖

```bash
cd /mnt/f/bigsinger/agent-practice/mcp-demo
pip install -r requirements.txt
```

> 需要 Python 3.10+ 和 `mcp` 包（`pip install mcp`）

### 2. 一条命令启动完整链路

```bash
# 启动 API Service + MCP Server（stdio 模式，等待 Hermes 连接）
python run_all.py
```

启动后会自动启动后端 API 服务（端口 8001），然后前台进入 MCP Server 的 stdio 模式，等待 Hermes Agent 连接。

### 3. 验证 API 服务

```bash
# 另开一个终端，确认 API 正常运行
curl http://127.0.0.1:8001/health
# → {"status": "ok", "service": "api-service"}

curl http://127.0.0.1:8001/api/users/u001
# → {"id": "u001", "name": "张三", "phone": "13812348888", ...}
```

---

## 与 Hermes Agent 集成

### 1. 添加 MCP 服务器配置

编辑 `~/.hermes/config.yaml`，在文件末尾添加 MCP 服务器配置（新版 Hermes 使用 `mcp_servers:` 顶层键）：

```yaml
mcp_servers:
  # 方案 A：无安全措施的原始包装
  demo-api-wrapper:
    command: python
    args:
      - /mnt/f/bigsinger/agent-practice/mcp-demo/mcp_server.py
    enabled: true

  # 方案 B：安全网关版（推荐用于演示）
  demo-security-gateway:
    command: python
    args:
      - /mnt/f/bigsinger/agent-practice/mcp-demo/mcp_gateway.py
    enabled: true
```

> ⚠️ **注意**：新版 Hermes（2026年5月后）的 MCP 配置使用顶层键 `mcp_servers:`，而非 `mcp.servers:`。路径使用 WSL 绝对路径（`/mnt/f/...`）。

### 2. 注册 MCP 服务器

添加配置后，通过 CLI 注册并连接：

```bash
# 注册并连接（会自动检测工具列表）
echo "Y" | hermes mcp add demo-api-wrapper --command python --args /mnt/f/bigsinger/agent-practice/mcp-demo/mcp_server.py
echo "Y" | hermes mcp add demo-security-gateway --command python --args /mnt/f/bigsinger/agent-practice/mcp-demo/mcp_gateway.py
```

### 3. 验证连接

```bash
hermes mcp list
# 输出示例:
#   Name               Transport                        Tools        Status
#   ───────────────── ──────────────────────────────── ──────────── ──────────
#   demo-api-wrapper   python /mnt/f/bigsinger/a...    all          ✓ enabled
#   demo-security-...  python /mnt/f/bigsinger/a...    all          ✓ enabled
```

### 4. 在 Hermes chat 中测试

确认 API 服务已启动，然后新开一个 Hermes 会话：

```bash
# 启动后端 API（保持运行）
python /mnt/f/bigsinger/agent-practice/mcp-demo/api_service.py

# 新开 Hermes 会话（MCP 工具在会话启动时加载）
hermes chat
```

在 chat 中提问：

```text
用 demo-api-wrapper 查询用户 u001 的信息
用 demo-security-gateway 查询用户 u001 的信息（token: demo-token-2026）
用错误的 token 查询用户 u003，看看会返回什么
用 admin-token-2026 查询订单 ord001
```

> **注意**：安全网关的每个工具都需要传入 `token` 参数。Hermes Agent 的 LLM 会根据工具 Schema 自动识别参数并填入。如果提问时未提供 token，LLM 可能会询问你要使用哪个 token。

---

## 全链路调用流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Hermes Agent                                  │
│  用户输入 "查询张三的信息"                                              │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ 通过 stdio 调用 MCP Tool
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Security Gateway (mcp_gateway.py)                  │
│                                                                      │
│  1. 日志: [INFO] 工具调用: get_user_info_safe(user_id='u001')        │
│  2. 向前端 API 发起 HTTP 请求                                         │
│  3. 脱敏: 138****8888, z****@internal.com                            │
│  4. 安全检测: ✅ 通过 / ⚠️ 发现泄露                                   │
│  5. 返回脱敏后的 JSON 给 Hermes                                      │
└──────────────┬──────────────────────────────────────────────────────┘
               │ HTTP GET /api/users/u001
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        API Service (api_service.py)                   │
│                                                                      │
│  Port 8001 · 模拟企业内部 REST API                                   │
│  返回原始数据（含手机号、邮箱等敏感字段）                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 实测数据对比

以下是 2026-05-22 在 Hermes Agent 中执行的实际测试结果。

### 前置条件

| 服务 | 状态 |
|------|------|
| `api_service.py` | 运行于 `http://127.0.0.1:8001` ✅ |
| `demo-api-wrapper` | 已注册 5 个 MCP Tool ✅ |
| `demo-security-gateway` | 已注册 5 个 MCP Tool（安全版） ✅ |

### 1. API Service 原始数据

```bash
curl http://127.0.0.1:8001/api/users/u001
```

```json
{
  "id": "u001",
  "name": "张三",
  "phone": "13812348888",          ← 明文
  "email": "zhangsan@internal.com" ← 明文
}
```

### 2. demo-api-wrapper（MCP 包装，无安全措施）

通过 Hermes Agent 调用 `get_user_info("u001")`：

```json
{
  "id": "u001",
  "name": "张三",
  "phone": "13812348888",          ← 明文透传
  "email": "zhangsan@internal.com" ← 明文透传
}
```

### 3. demo-security-gateway（MCP 安全网关）

通过 Hermes Agent 调用 `get_user_info_safe("u001")`：

```json
{
  "id": "u001",
  "name": "张三",
  "phone": "138****8888",          ✅ 脱敏
  "email": "z****@internal.com"    ✅ 脱敏
}
```

### 4. 网关日志输出（`gateway_access.log`）

真实日志记录：

```
2026-05-22 14:31:54 | INFO | 工具调用: get_user_info_safe(user_id='u001')
2026-05-22 14:31:54 | INFO | 响应大小: 122 字符
2026-05-22 14:31:54 | INFO | 安全检查: 通过
```

### 5. Token 认证测试（v2 新增）

网关 v2 要求每次工具调用必须携带有效 Token。

**有效 Token 列表**：

| Token | 级别 | 说明 |
|-------|------|------|
| `demo-token-2026` | standard | 标准权限 Demo |
| `admin-token-2026` | admin | 管理员权限 |

**场景 A — 无效 Token（拒绝）**：

```json
// 调用: get_user_info_safe(token="wrong-token", user_id="u001")
{
  "error": "unauthorized",
  "message": "无效的 token，请使用有效 Token",
  "hint": ["demo-token-2026", "admin-token-2026"]
}
```

**场景 B — 有效 Token（放行+脱敏）**：

```json
// 调用: get_user_info_safe(token="demo-token-2026", user_id="u001")
{
  "id": "u001",
  "name": "张三",
  "phone": "138****8888",          ✅ 脱敏
  "email": "z****@internal.com"    ✅ 脱敏
}
```

**场景 C — Admin Token 查询订单**：

```json
// 调用: get_order_info_safe(token="admin-token-2026", order_id="ord001")
{
  "id": "ord001",
  "user_id": "u001",
  "product": "MCP Server Pro",
  "amount": 2999.0,
  "status": "已支付",
  "date": "2026-05-20"
}
```

**网关日志中的认证记录**：

```log
WARNING | [认证失败] 无效 token (前缀: wrong-...)
INFO    | [认证成功] token=Demo Token（标准权限）, 级别=standard
INFO    | [认证成功] token=Admin Token（管理员权限）, 级别=admin
```

### 6. 对比总结（v2）

| 对比维度 | API Service | demo-api-wrapper | demo-security-gateway |
|----------|-------------|------------------|-----------------------|
| Token 认证 | ❌ 无认证 | ❌ 无认证 | ✅ 需有效 Token |
| 手机号 | 明文 | 明文透传 | `138****8888` 脱敏 |
| 邮箱 | 明文 | 明文透传 | `z****@internal.com` 脱敏 |
| 调用日志 | ❌ 默认静默 | ❌ 默认静默 | ✅ 记入 `gateway_access.log` |
| 安全检测 | ❌ | ❌ | ✅ 输出内容扫描 |
| 协议 | HTTP REST | MCP stdio | MCP stdio |

### 安全网关日志示例

运行安全网关后，查看 `gateway_access.log` 可以看到每次调用的完整记录：

```log
2026-05-22 14:31:54 | INFO | 工具调用: get_user_info_safe(user_id='u001')
2026-05-22 14:31:54 | INFO | 响应大小: 122 字符
2026-05-22 14:31:54 | INFO | 安全检查: 通过
```

多个工具调用产生的日志：

```log
2026-05-22 14:31:54 | INFO | 工具调用: get_user_info_safe(user_id='u001')
2026-05-22 14:31:54 | INFO | 响应大小: 122 字符
2026-05-22 14:31:54 | INFO | 安全检查: 通过
2026-05-22 14:32:05 | INFO | 工具调用: get_order_info_safe(order_id='ord001')
2026-05-22 14:32:05 | INFO | 响应大小: 112 字符 | 告警数: 0
2026-05-22 14:32:05 | INFO | 安全检查: 通过
```

> **脱敏策略说明**：
> - 手机号 → 保留前3位和后4位，中间掩码（`138****8888`）
> - 邮箱 → 仅保留首字母和域名首字母（`z****@internal.com`）
> - 身份证号 → 保留前6位和后4位，其余掩码

---

## 扩展练习

完成基础演示后，可以尝试以下进阶练习：

1. **新增数据源**：在 `api_service.py` 中新增模拟数据（如产品目录、工单），并在 MCP 中注册对应工具

2. ~~添加身份验证~~ ✅ **已在 v2 中实现**：安全网关已集成 Token 认证机制。可进一步尝试：
   - 将 Token 改为 JWT 格式，验证签名而非简单字符串匹配
   - 实现 Token 级别权限控制（如 standard 级别不能查询订单金额，仅 admin 可查）
   - 实现 Token 过期机制（`exp` 字段）
   - 将 Token 通过 MCP 的 `capabilities` 或 `initialization` 阶段注入，而非每个工具参数传入

3. **添加阻断机制**：当安全检测发现高危内容时（如 Token 被滥用、脱敏逻辑失效），**阻断返回**并返回错误信息而非脱敏数据

4. **改成 SSE 模式**：用 `python mcp_server.py --sse` 或 `python mcp_gateway.py --sse` 启动 SSE 模式，在浏览器中观察 MCP Server 的实时日志

5. **资源（Resource）和提示（Prompt）**：研究 MCP 的 Resource 和 Prompt 概念，在本项目中添加 `@mcp.resource()` 和 `@mcp.prompt()` 演示
