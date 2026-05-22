"""
Module 1 — Simulated API Service
==================================
A minimal REST API built on stdlib http.server (zero external deps).
Simulates internal services that an Agent/MCP might query.
"""

import json
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
PORT = 8001

# ── Mock Data ──────────────────────────────────────────────
USERS = {
    "u001": {"id": "u001", "name": "张三", "phone": "13812348888",
             "email": "zhangsan@internal.com", "role": "工程师",
             "department": "AI 平台部"},
    "u002": {"id": "u002", "name": "李四", "phone": "13987654321",
             "email": "lisi@internal.com", "role": "产品经理",
             "department": "创新业务部"},
    "u003": {"id": "u003", "name": "王五", "phone": "13655557777",
             "email": "wangwu@internal.com", "role": "安全研究员",
             "department": "信息安全部"},
}

ORDERS = {
    "ord001": {"id": "ord001", "user_id": "u001", "product": "MCP Server Pro",
               "amount": 2999.00, "status": "已支付", "date": "2026-05-20"},
    "ord002": {"id": "ord002", "user_id": "u001", "product": "Agent SDK Enterprise",
               "amount": 15999.00, "status": "处理中", "date": "2026-05-21"},
    "ord003": {"id": "ord003", "user_id": "u002", "product": "AI Gateway Standard",
               "amount": 499.00, "status": "已发货", "date": "2026-05-19"},
}

WEATHER = {
    "北京": {"city": "北京", "temperature": 28, "humidity": 45, "condition": "晴"},
    "上海": {"city": "上海", "temperature": 26, "humidity": 72, "condition": "多云"},
    "深圳": {"city": "深圳", "temperature": 31, "humidity": 80, "condition": "阵雨"},
    "杭州": {"city": "杭州", "temperature": 25, "humidity": 68, "condition": "阴"},
}


def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def not_found(handler, msg="Not Found"):
    json_response(handler, {"error": msg}, 404)


class APIHandler(BaseHTTPRequestHandler):
    """Routes GET requests to mock endpoints."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = urllib.parse.unquote(parsed.path.rstrip("/"))
        params = parse_qs(parsed.query)

        try:
            # /api/users/{id}
            m = re.match(r"^/api/users/(\w+)$", path)
            if m:
                uid = m.group(1)
                if uid in USERS:
                    return json_response(self, USERS[uid])
                return not_found(self, f"用户 {uid} 不存在")

            # /api/orders/{id}
            m = re.match(r"^/api/orders/(\w+)$", path)
            if m:
                oid = m.group(1)
                if oid in ORDERS:
                    return json_response(self, ORDERS[oid])
                return not_found(self, f"订单 {oid} 不存在")

            # /api/orders/by-user/{uid}
            m = re.match(r"^/api/orders/by-user/(\w+)$", path)
            if m:
                uid = m.group(1)
                user_orders = [o for o in ORDERS.values() if o["user_id"] == uid]
                return json_response(self, user_orders)

            # /api/weather/{city}
            m = re.match(r"^/api/weather/(.+)$", path)
            if m:
                city = m.group(1)
                if city in WEATHER:
                    return json_response(self, WEATHER[city])
                return not_found(self, f"城市 {city} 不存在")

            # /api/search
            if path == "/api/search":
                q = params.get("q", [""])[0].lower()
                results = []
                for u in USERS.values():
                    if q in u["name"].lower() or q in u["department"].lower():
                        results.append({"type": "user", "data": u})
                for o in ORDERS.values():
                    if q in o["product"].lower():
                        results.append({"type": "order", "data": o})
                return json_response(self, {"query": q, "results": results})

            # Health check
            if path == "/health":
                return json_response(self, {"status": "ok", "service": "api-service"})

            not_found(self, f"未知路径: {path}")

        except Exception as e:
            json_response(self, {"error": str(e)}, 500)

    def log_message(self, format, *args):
        """Suppress default logging; we'll log via gateway instead."""
        pass


def start_api_server(host=HOST, port=PORT):
    server = HTTPServer((host, port), APIHandler)
    print(f"[API Service] 启动于 http://{host}:{port}")
    print(f"  可用端点:")
    print(f"    GET /api/users/{{id}}        — 用户信息")
    print(f"    GET /api/orders/{{id}}        — 订单信息")
    print(f"    GET /api/orders/by-user/{{id}} — 用户订单列表")
    print(f"    GET /api/weather/{{city}}     — 天气查询")
    print(f"    GET /api/search?q=xxx         — 综合搜索")
    print(f"    GET /health                   — 健康检查")
    server.serve_forever()


if __name__ == "__main__":
    start_api_server()
