import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.main import rag
if len(sys.argv)<3:raise SystemExit("usage: python scripts/retrieve_rag.py <mcId> <facts text>")
mc=int(sys.argv[1]); retrieved=rag(mc,[sys.argv[2]],"\0offline-query-exclusion-key")
print(json.dumps({"mcId":mc,"retrieved":[{"example_id":x["example_id"],"score":x["score"]} for x in retrieved]},ensure_ascii=True,indent=2))
