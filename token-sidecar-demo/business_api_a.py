"""
Business API-A v3 — 用户服务（返回用户感知数据）
"""
import asyncio, logging, httpx, uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header

logging.basicConfig(level=logging.INFO,format="%(asctime)s [API-A] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("api-a")

try:
    import jwt as pyjwt; from jwt import PyJWTError
except ImportError: raise

app=FastAPI(title="API-A User Service",version="3.0")
_pub_key="";_kid=""

async def fetch_pk():
    global _pub_key,_kid
    async with httpx.AsyncClient() as c:
        r=await c.get("http://localhost:28001/public-key",timeout=5);r.raise_for_status()
        d=r.json();_kid=d["kid"];_pub_key=d["public_key"];log.info("公钥就绪 | kid=%s",_kid)

@app.on_event("startup")
async def startup():
    for i in range(10):
        try: await fetch_pk();return
        except: log.warning("等沙箱 (try %d/10)...",i+1);await asyncio.sleep(1)
    raise RuntimeError("沙箱未就绪")

async def verify_token(authorization:str=Header(None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"无令牌")
    t=authorization.split(" ",1)[1]
    try:
        p=pyjwt.decode(t,_pub_key,algorithms=["RS256"],audience="api-a")
        log.info("验证通过 | sub=%s | scope=%s | user=%s",p.get("sub"),p.get("scope"),p.get("user_info",{}).get("user_id","?"))
        return p
    except pyjwt.ExpiredSignatureError: raise HTTPException(401,"令牌过期")
    except PyJWTError as e: raise HTTPException(401,f"令牌无效: {e}")

@app.get("/protected-data")
async def protected_data(payload:dict=Depends(verify_token)):
    ui=payload.get("user_info",{})
    uid=ui.get("user_id","unknown");name=ui.get("name","未知用户")
    role=ui.get("role","unknown");dept=ui.get("dept","未知")

    # 不同部门看到的数据不同
    users={
        "dev_zhang":{"name":"张工","email":"zhang@starcloud.com","project":"Agent Platform"},
        "dev_liu":{"name":"刘工","email":"liu@starcloud.com","project":"IAM Service"},
        "dev_chen":{"name":"陈工","email":"chen@starcloud.com","project":"Data Pipeline"},
        "dev_zhao":{"name":"赵工","email":"zhao@starcloud.com","project":"- 实习期"},
    }
    team_data=[v for k,v in users.items()] if dept=="研发部" else [{"name":name,"email":ui.get("email",""),"project":"-"}]

    log.info("返回用户数据 | user=%s role=%s",uid,role)
    return {
        "service":"API-A (User Service)","success":True,
        "requester":{"user_id":uid,"name":name,"role":role,"dept":dept},
        "team_members":team_data,
        "token_info":{"audience":payload.get("aud"),"scope":payload.get("scope"),
                      "issuer":payload.get("iss"),"expires_at":payload.get("exp")},
    }

@app.get("/health")
async def health():return {"status":"ok","kid":_kid}

if __name__=="__main__":uvicorn.run(app,host="0.0.0.0",port=28100)
