"""
One-Click Launcher — 一键启动完整链路
======================================
启动顺序：
  1. API Service  (模拟后端服务)
  2. 输出 MCP Server 连接指令

用法:
  python run_all.py [--gateway] [--sse]

选项:
  --gateway  启动安全网关版 MCP Server（含脱敏+日志+检测）
  --sse      以 SSE 模式启动 MCP Server（浏览器可调试）
"""

import sys
import os
import subprocess
import signal
import time
import atexit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

processes = []
USE_GATEWAY = "--gateway" in sys.argv
USE_SSE = "--sse" in sys.argv


def start_process(script_name, label, background=True):
    path = os.path.join(BASE_DIR, script_name)
    cmd = [sys.executable, path]
    if USE_SSE:
        cmd.append("--sse")

    if background:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
        )
        processes.append(proc)
        print(f"  [{label}] PID={proc.pid} 已启动")
        return proc
    else:
        # 前台运行（替换当前进程）
        os.execvp(sys.executable, cmd)


def cleanup():
    print("\n正在停止所有服务...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    print("所有服务已停止。")


def wait_for_ready(url, timeout=10):
    """轮询等待 API 服务就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


if __name__ == "__main__":
    atexit.register(cleanup)

    print("=" * 55)
    print("  MCP Demo — 一键启动")
    print("=" * 55)
    print()

    # Step 1: Start API Service
    print("[1/2] 启动 API Service (模拟后端)...")
    start_process("api_service.py", "API Service")
    time.sleep(1)

    # Wait for API to be ready
    if not wait_for_ready("http://127.0.0.1:8001/health"):
        print("[!] API 服务启动超时，请检查端口 8001 是否被占用")
        sys.exit(1)
    print("  ✅ API Service 就绪于 http://127.0.0.1:8001")
    print()

    # Step 2: Start MCP Server
    if USE_GATEWAY:
        print("[2/2] 启动 MCP 安全网关...")
        mcp_script = "mcp_gateway.py"
        mcp_label = "Security Gateway"
    else:
        print("[2/2] 启动 MCP Wrapper Server...")
        mcp_script = "mcp_server.py"
        mcp_label = "Wrapper Server"

    if USE_SSE:
        start_process(mcp_script, mcp_label, background=True)
        print()
        print(f"  🌐 SSE 模式: 浏览器访问 http://127.0.0.1:8000/sse")
        print()
        print("  按 Ctrl+C 停止所有服务")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        # stdio mode — MCP server takes over the foreground
        print(f"  MCP Server 已在 stdio 模式下运行 (PID={os.getpid()})")
        print()
        print("  📋 在 Hermes Agent 的 config.yaml 中添加:")
        print(f'     command: python')
        print(f'     args: ["{mcp_script.replace(".py", "")}"]')
        print()
        print("  按 Ctrl+C 停止")
        print()

        # Start MCP server in foreground (it replaces this process)
        start_process(mcp_script, mcp_label, background=False)
