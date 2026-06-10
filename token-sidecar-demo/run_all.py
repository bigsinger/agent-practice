"""
一键启动编排脚本 v2 — 5 个进程
  沙箱(:8001) → API-A(:8100) → API-B(:8200) → Sidecar(:9000)
"""

import subprocess
import sys
import os
import time
import signal

os.chdir(os.path.dirname(os.path.abspath(__file__)))

processes = []
service_info = []


def start_service(name, script, port, wait=3):
    log_file = open(f"{name}.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, script],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        if sys.platform == "win32" else 0,
    )
    processes.append((proc, name, log_file))
    service_info.append(f"  {name:<16} http://localhost:{port}")
    print(f"  ▶ 启动 {name} (PID={proc.pid})...", end="", flush=True)
    time.sleep(wait)
    print(" ✓")


def cleanup():
    print("\n\n⏹  停止所有服务...")
    for proc, name, log_file in reversed(processes):
        print(f"  ▶ 停止 {name} (PID={proc.pid})")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
    print(" ✓ 已停止")


def main():
    print("═" * 55)
    print("  Token Sidecar Demo v2 — 透明拦截 · 多 API")
    print("═" * 55)
    print()

    try:
        print("步骤 1/4: 沙箱 (Token Vault)")
        start_service("sandbox", "sandbox.py", 28001, wait=3)

        print("步骤 2/4: 业务 API-A（用户服务）")
        start_service("api-a", "business_api_a.py", 28100, wait=2)

        print("步骤 3/4: 业务 API-B（订单服务）")
        start_service("api-b", "business_api_b.py", 28200, wait=2)

        print("步骤 4/4: Sidecar 代理")
        start_service("sidecar", "sidecar.py", 29000, wait=2)

        print()
        print("─" * 55)
        print("  ✅ 全部就绪！")
        print()
        for info in service_info:
            print(info)
        print()
        print("  新开终端运行测试:")
        print("    python requester.py")
        print()
        print("  Ctrl+C 停止所有服务")
        print("─" * 55)
        print()

        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
