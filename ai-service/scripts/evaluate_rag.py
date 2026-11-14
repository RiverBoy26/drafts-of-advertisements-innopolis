"""Offline retrieval report. Quality scores require a human-labeled query JSONL."""
import argparse, json, re, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import rag

def read_jsonl(path):
    rows=[]
    for no,line in enumerate(path.read_text(encoding="utf8").splitlines(),1):
        if not line.strip():continue
        try:rows.append(json.loads(line))
        except json.JSONDecodeError as exc:raise ValueError(f"{path}:{no}: malformed JSON: {exc.msg}") from exc
    return rows

def tokens(s):return set(re.findall(r"\w+",re.sub(r"\s+"," ",s.lower().replace("ё","е"))))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--corpus",type=Path,default=ROOT/"data/curated_rag_examples.jsonl")
    parser.add_argument("--queries",type=Path,help="Human-labeled JSONL: mcId, source_facts, relevant_example_ids")
    args=parser.parse_args(); corpus=read_jsonl(args.corpus)
    report={"corpus_entries":len(corpus),"verified_entries":sum(x.get("verified") is True for x in corpus),"near_duplicate_threshold_jaccard":.9,"profiles":{}}
    for name,description in {
        "G0":"generation without retrieval",
        "G1":"lexical retrieval without production provenance/near-duplicate filters (unsafe diagnostic baseline)",
        "G2":"production category + verified human-review + near-duplicate filters",
        "G3":"G2 retrieval plus style-only prompt constraint; generation requires live provider calls",
    }.items():report["profiles"][name]={"description":description,"quality":"NOT_MEASURED"}
    if not args.queries or not args.queries.exists():
        report["status"]="NOT_MEASURED"
        report["reason"]="No human-labeled query set supplied; curated corpus is empty unless reviewers add approved examples. No relevance or generation quality is inferred from self-retrieval."
        if args.queries and not args.queries.exists():report["reason"]="Human-labeled query file does not exist."
        print(json.dumps(report,ensure_ascii=False,indent=2));return
    queries=read_jsonl(args.queries)
    required=("mcId","source_facts","relevant_example_ids")
    if any(not isinstance(q,dict) or any(k not in q for k in required) for q in queries):raise ValueError("Each query needs mcId, source_facts and relevant_example_ids")
    profiles={"G0":[],"G1":[],"G2":[],"G3":[]}
    for q in queries:
        relevant=set(q["relevant_example_ids"]); query_tokens=tokens(q["source_facts"])
        candidates=[x for x in corpus if x.get("mcId")==q["mcId"]]
        lexical=[]
        for x in candidates:
            other=tokens(x.get("source_facts","")); score=len(query_tokens&other)/max(1,len(query_tokens|other))
            lexical.append((score,x))
        lexical.sort(key=lambda pair:(-pair[0],str(pair[1].get("example_id",""))))
        profiles["G0"].append([])
        profiles["G1"].append([x.get("example_id") for score,x in lexical[:2] if score>0])
        production=rag(q["mcId"],[q["source_facts"]],"\0offline-eval-query",args.corpus)
        ids=[x["example_id"] for x in production]
        profiles["G2"].append(ids);profiles["G3"].append(ids)
    for name,results in profiles.items():
        ps=[];rs=[]
        for query,got in zip(queries,results):
            gold=set(query["relevant_example_ids"]); selected=set(got)
            ps.append(len(gold&selected)/max(1,len(selected)));rs.append(len(gold&selected)/max(1,len(gold)))
        report["profiles"][name].update({"status":"RETRIEVAL_ONLY","queries":len(queries),"precision_at_2":sum(ps)/len(ps) if ps else None,"recall_at_2":sum(rs)/len(rs) if rs else None})
    report["status"]="MEASURED_RETRIEVAL_ONLY"
    report["note"]="G3 generation quality, claims, latency and cost are not measured by offline retrieval; evaluate these with blinded live outputs."
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
