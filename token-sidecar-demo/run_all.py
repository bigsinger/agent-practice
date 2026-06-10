"""
一键启动 v4 — 6 个进程：初始化DB → IAM(:27000) → 门户(:26000) → 沙箱 → 双API → Sidecar
"""
import subprocess,sys,os,time,signal
os.chdir(os.path.dirname(os.path.abspath(__file__)))
processes=[]

def start(name,script,port="",wait=3):
    f=open(f"{name}.log","w",encoding="utf-8")
    p=subprocess.Popen([sys.executable,script],stdout=f,stderr=subprocess.STDOUT)
    processes.append((p,name,f))
    s=f"  ▶ {name}"+(f" (:→{port})" if port else "")
    print(f"{s}...",end="",flush=True);time.sleep(wait);print(" ✓")

def cleanup():
    print("\n⏹  停止...")
    for p,n,f in reversed(processes):
        p.terminate()
        try: p.wait(3)
        except: p.kill()
        f.close()
    print(" ✓")

def main():
    print("═"*55)
    print("  星辰科技 v4 — IAM + Vault + Portal + SOC")
    print("═"*55);print()
    try:
        print("0/6: 初始化 SQLite 数据库");start("seed","seed_data.py","",2)
        print("1/6: IAM 系统");  start("iam","iam.py","27000",3)
        print("2/6: 管理门户");  start("portal","portal.py","26000",2)
        print("3/6: 沙箱(Vault)");start("vault","sandbox.py","28001",3)
        print("4/6: API-A + API-B");start("api-a","business_api_a.py","28100",2);start("api-b","business_api_b.py","28200",2)
        print("5/6: Sidecar 代理");start("sidecar","sidecar.py","29000",2)
        print();print("─"*55)
        print("  ✅ 全部就绪！")
        print("  登录页  → http://localhost:27000")
        print("  门户    → http://localhost:26000/portal/login")
        print("  IAM     → http://localhost:27000")
        print("  Vault   → http://localhost:28001")
        print("  API-A   → http://localhost:28100")
        print("  API-B   → http://localhost:28200")
        print("  Sidecar → http://localhost:29000")
        print();print("  测试账号密码见 README.md")
        print("  Ctrl+C 停止");print("─"*55)
        signal.signal(signal.SIGINT,lambda s,f: sys.exit(0))
        signal.signal(signal.SIGTERM,lambda s,f: sys.exit(0))
        while True: time.sleep(1)
    except KeyboardInterrupt: pass
    finally: cleanup()

if __name__=="__main__": main()
