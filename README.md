# Agent & Security Practice

> 一个 Agent 与安全技术的实践学习项目，每个练习以独立子目录存放源码和 README。

## 结构

```
agent-practice/
├── README.md              # 本文件，项目总览
├── .gitignore
├── requirements.txt       # 公共依赖（各 demo 可自建 .venv 或引用此处）
└── <demo-name>/           # 每个 demo 独立目录
    ├── README.md          # 必含：功能说明、运行方式、依赖
    ├── *.py               # 源码
    └── requirements.txt   # 可选：demo 级依赖
```

## Demo 一览

| Demo | 说明 | 技术栈 |
|------|------|--------|
| [mcp-demo](./mcp-demo) | MCP 协议网关与服务端实现 | Python, FastAPI |
| [token-sidecar-demo](./token-sidecar-demo) | Sidecar 模式——请求拦截与密钥/令牌置换 | Python, FastAPI, JWT |

> 持续新增中...

## 环境要求

- Python 3.10+
- Windows 10+（主开发环境，部分场景可用 WSL 作为补充）

## 约定

1. 每个 demo 必须是**可独立运行**的，有明确的 README 说明启动方式
2. 避免 demo 间交叉依赖
3. 涉及 API Key 等敏感信息放在 `.env`，不提交
