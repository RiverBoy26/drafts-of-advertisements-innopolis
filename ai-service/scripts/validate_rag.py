import json,re,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"data/curated_rag_examples.jsonl"
seen=set(); normalized=set(); verified_rows=[]; errors=[]; count=0; verified=0
for no,line in enumerate(path.read_text(encoding="utf8").splitlines(),1):
    if not line.strip():continue
    count+=1
    try:x=json.loads(line)
    except Exception:errors.append(f"line {no}: malformed JSON");continue
    required=("example_id","mcId","source_facts","approved_title","approved_text","verified","origin","version")
    if not isinstance(x,dict) or any(k not in x for k in required):errors.append(f"line {no}: missing field or non-object row");continue
    valid_id=isinstance(x["example_id"],str) and bool(x["example_id"].strip())
    if not valid_id:errors.append(f"line {no}: invalid example_id")
    elif x["example_id"] in seen:errors.append(f"line {no}: duplicate example_id")
    if type(x["mcId"]) is not int or x["mcId"] not in range(101,107):errors.append(f"line {no}: invalid mcId")
    if type(x["verified"]) is not bool:errors.append(f"line {no}: verified must be boolean")
    if not isinstance(x["version"],str) or not x["version"].strip():errors.append(f"line {no}: invalid version")
    if x["verified"] is True and x["origin"]!="human_reviewed_author":errors.append(f"line {no}: unapproved verified origin")
    if x["verified"] is True:
        verified+=1
        valid_content=all(isinstance(x[k],str) and x[k].strip() for k in ("source_facts","approved_title","approved_text"))
        if not valid_content:errors.append(f"line {no}: blank or invalid approved content")
        if not valid_content:continue
        sig=hashlib.sha256(re.sub(r"\s+"," ",x["source_facts"].lower()).encode()).hexdigest()
        if sig in normalized:errors.append(f"line {no}: duplicate source_facts")
        normalized.add(sig)
        verified_rows.append((no,x))
        if re.search(r"garanti|skidk|besplat|stazh|licenzi|opyt|гарант|скид|бесплат",x["approved_text"].lower()):errors.append(f"line {no}: review claims/unsupported-promises phrase")
    if valid_id:seen.add(x["example_id"])
def tokens(s):return set(re.findall(r"\w+",re.sub(r"\s+"," ",s.lower().replace("ё","е"))))
for ix,(line_a,a) in enumerate(verified_rows):
    ta=tokens(a["source_facts"])
    for line_b,b in verified_rows[ix+1:]:
        if a["mcId"]!=b["mcId"]:continue
        tb=tokens(b["source_facts"]); similarity=len(ta&tb)/max(1,len(ta|tb))
        if similarity>=.9:errors.append(f"lines {line_a},{line_b}: near-duplicate verified source_facts (Jaccard {similarity:.3f})")
print(json.dumps({"path":str(path),"entries":count,"verified_entries":verified,"errors":errors,"valid":not errors},ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
