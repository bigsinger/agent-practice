"""
一键启动 v3 — 5 个进程：IAM(:27000) → 沙箱(:28001) → API-A(:28100) → API-B(:28200) → Sidecar(:29000)
"""
import subprocess,sys,os,time,signal

os.chdir(os.path.dirname(os.path.abspath(__file__)))
processes=[]

def start(name,script,port,wait=3):
    f=open(f"{name}.log","w",encoding="utf-8")
    p=subprocess.Popen([sys.executable,script],stdout=f,stderr=subprocess.STDOUT)
    processes.append((p,name,f))
    print(f"  ▶ {name} (:→{port})...",end="",flush=True)
    time.sleep(wait);print(" ✓")

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
    print("  Sidecar v3 — IAM + Vault + 透明令牌注入")
    print("═"*55);print()
    try:
        print("1/5: IAM (身份与访问管理)"); start("iam","iam.py",27000,2)
        print("2/5: 沙箱 (Token Vault)");  start("vault","sandbox.py",28001,3)
        print("3/5: API-A (用户服务)");    start("api-a","business_api_a.py",28100,2)
        print("4/5: API-B (订单服务)");    start("api-b","business_api_b.py",28200,2)
        print("5/5: Sidecar (透明代理)");  start("sidecar","sidecar.py",29000,2)
        print();print("─"*55)
        print("  ✅ 全部就绪！")
        print("   iam      → http://localhost:27000")
        print("   vault    → http://localhost:28001")
        print("   api-a    → http://localhost:28100")
        print("   api-b    → http://localhost:28200")
        print("   sidecar  → http://localhost:29000")
        print();print("  新终端运行: python requester.py")
        print("  Ctrl+C 停止");print("─"*55)
        signal.signal(signal.SIGINT,lambda s,f: sys.exit(0))
        signal.signal(signal.SIGTERM,lambda s,f: sys.exit(0))
        while True: time.sleep(1)
    except KeyboardInterrupt: pass
    finally: cleanup()

if __name__=="__main__": main()
