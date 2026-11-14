import json,re,hashlib,statistics
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]; src=ROOT/"data/public-train-annotated.jsonl"
rows=[json.loads(x) for x in src.read_text(encoding="utf8").splitlines() if x.strip()]
def norm(s):return re.sub(r"\s+"," ",s.lower().replace(chr(0x451),chr(0x435))).strip()
groups=defaultdict(list)
for r in rows:groups[norm(r.get("description",""))].append(tuple(sorted({int(x["mcId"]) for x in r.get("found_microcategories",[])})))
conflicts=sum(1 for values in groups.values() if len(set(values))>1)
counts=Counter(int(x["mcId"]) for r in rows for x in r.get("found_microcategories",[]))
lengths=[len(r.get("description", "")) for r in rows]
print(json.dumps({"source":src.name,"rows":len(rows),"unique_normalized_descriptions":len(groups),"duplicate_rows":len(rows)-len(groups),"conflicting_label_groups":conflicts,"empty_descriptions":sum(not r.get("description","").strip() for r in rows),"label_counts":dict(sorted(counts.items())),"description_chars":{"min":min(lengths),"median":statistics.median(lengths),"p95":sorted(lengths)[int(.95*(len(lengths)-1))],"max":max(lengths)},"sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"label_source":"weak automated labels"},ensure_ascii=True,indent=2))
