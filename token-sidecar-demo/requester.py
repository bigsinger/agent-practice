"""
Requester（请求者）
--------------------
生产对标：调用多个微服务的外部客户端 / 上游服务

关键特性：请求者 **零感知** Sidecar 的存在。
  - 它不知道沙箱在哪里
  - 它不管理令牌
  - 它不做认证
  - 它只是发出 HTTP 请求，以为自己在直接调用业务 API

在本 demo 中，请求者通过 Sidecar(:9000) 访问两个 API：
  http://localhost:9000/api-a/protected-data  ← 它以为这是「API-A」的地址
  http://localhost:9000/api-b/protected-data  ← 它以为这是「API-B」的地址
"""

import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REQ ] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("requester")

try:
    import httpx
except ImportError:
    log.error("请安装 httpx: pip install httpx")
    raise

SIDECAR_URL = "http://localhost:29000"


def call_api(service_path: str, label: str):
    """
    向「以为的 API 地址」发起请求。
    请求者眼中：这是直接调用 API。
    实际：请求经过 Sidecar，被拦截并注入了令牌。
    """
    url = f"{SIDECAR_URL}{service_path}"

    log.info("─" * 50)
    log.info("请求者 → %s", url)
    log.info("  我的视角：直接调用 %s", label)
    log.info("  实际路径：请求被 Sidecar 拦截并注入令牌")

    # 请求者只发送业务参数，不做任何认证
    headers = {
        "X-Request-ID": "demo-trace-001",
        "Content-Type": "application/json",
    }

    with httpx.Client() as client:
        resp = client.get(url, headers=headers, timeout=10)

    log.info("  响应状态: %s", resp.status_code)

    try:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)

    print()
    return resp


def run_demo():
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║      Sidecar 透明拦截演示 — 请求者零感知              ║")
    log.info("║                                                         ║")
    log.info("║  请求者不知道 Sidecar 的存在，不管理任何令牌。          ║")
    log.info("║  Sidecar 自动识别目标 API，获取对应 JWT，注入转发。     ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("")

    # ====== 第一次：访问 API-A（用户数据） ======
    log.info("▶ 演示 1：访问 API-A（用户服务）")
    log.info("  Sidecar 将自动获取 audience=api-a 的 JWT 并注入")
    call_api("/api-a/protected-data", "API-A (User Service)")

    # ====== 第二次：访问 API-B（订单数据） ======
    log.info("▶ 演示 2：访问 API-B（订单服务）")
    log.info("  Sidecar 将自动获取 audience=api-b 的 JWT 并注入")
    call_api("/api-b/protected-data", "API-B (Order Service)")

    # ====== 第三次：再次访问 API-A（验证缓存命中） ======
    log.info("▶ 演示 3：再次访问 API-A（令牌缓存命中）")
    log.info("  Sidecar 发现缓存中已有 audience=api-a 的有效令牌，直接复用")
    call_api("/api-a/protected-data", "API-A (User Service) — 二次请求")

    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║  演示完成                                              ║")
    log.info("║                                                         ║")
    log.info("║  请求者全程没有：                                       ║")
    log.info("║  • 管理或刷新令牌                                       ║")
    log.info("║  • 知道沙箱的存在                                       ║")
    log.info("║  • 修改请求头                                          ║")
    log.info("║                                                         ║")
    log.info("║  所有安全逻辑由 Sidecar 透明完成。                      ║")
    log.info("╚══════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    run_demo()
