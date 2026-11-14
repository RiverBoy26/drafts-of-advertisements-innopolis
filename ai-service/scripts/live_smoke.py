import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if os.getenv("ENABLE_LIVE_API_TESTS","false").lower()!="true":
    print(json.dumps({"status":"NOT_RUN","reason":"Set ENABLE_LIVE_API_TESTS=true to permit a paid request."}));raise SystemExit(0)
if not os.getenv("DEEPSEEK_API_KEY"):
    print(json.dumps({"status":"NOT_RUN_NO_KEY"}));raise SystemExit(0)
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
sample={"description":"Укладываю плитку и устанавливаю розетки в квартирах.","mcId":101}
r=client.post("/internal/v1/avito/drafts",json=sample)
diag=getattr(app.state,"diagnostics",[])[-1] if getattr(app.state,"diagnostics",[]) else None
print(json.dumps({"status":"LIVE_RESPONSE" if r.status_code==200 else "LIVE_ERROR","httpStatus":r.status_code,"response":r.json(),"diagnostics":diag},ensure_ascii=True,indent=2))
