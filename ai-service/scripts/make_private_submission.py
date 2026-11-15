"""Build a parseable classification submission from the local intent-context ensemble."""
from __future__ import annotations

import csv
import json
import re
import sys
import argparse
from pathlib import Path

import joblib
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import norm, explicitly_negated
from app.transformer_classifier import ProbabilityBlend, RuBertClassifier
from advertisement_lexicon import LEX

OUTPUT=ROOT.parent/"outputs/private-test-submission-intent-context.csv"
IDS=(102,103,104,105,106)
NAMES={102:"Штукатурные работы",103:"Плиточные работы",104:"Сантехнические работы",105:"Электромонтажные работы",106:"Обои и малярные работы"}

def excerpt(text,category):
    clean=re.sub(r"\s+"," ",text).strip()
    match=LEX[category].search(clean)
    if match:
        start=max(0,match.start()-180)
        end=min(len(clean),match.end()+420)
        part=clean[start:end]
        if start:part="…"+part
        if end<len(clean):part+="…"
    else:
        part=clean[:600]+("…" if len(clean)>600 else "")
    return NAMES[category]+". "+part

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--private-csv",type=Path,required=True,help="Path to the private input CSV; it is not stored in this repository")
    parser.add_argument("--output",type=Path,default=None,help="Optional output path for the submission CSV")
    parser.add_argument("--adaptive",action="store_true",help="Use 55% RuBERT for <=512 tokens, 45% for longer ads")
    parser.add_argument("--scope",action="store_true",help="Use the separately trained offer-scope candidate")
    parser.add_argument("--short-threshold",type=float,default=.525)
    args=parser.parse_args()
    data=pd.read_csv(args.private_csv,dtype=str,keep_default_na=False)
    assert list(data.columns)==["testcase","description"] and data.testcase.is_unique
    variant="intent_scope" if args.scope else "intent_context"
    cpu=joblib.load(ROOT/f"artifacts/cpu_char_{variant}.joblib")["model"]
    bert=RuBertClassifier(str(ROOT/f"artifacts/rubert_{variant}"))
    texts=[norm(x) for x in data.description]
    if args.adaptive:
        import numpy as np
        cpu_scores=cpu.predict_proba(texts)
        bert_scores=bert.predict_proba(texts)
        token_lengths=[len(ids) for ids in bert.tokenizer(texts,add_special_tokens=True,truncation=False)["input_ids"]]
        weights=np.asarray([.55 if n<=512 else .45 for n in token_lengths])[:,None]
        scores=(1-weights)*cpu_scores+weights*bert_scores
        if args.scope:
            output=ROOT.parent/"outputs/private-test-submission-scope-adaptive.csv"
        elif args.short_threshold!=.525:
            output=ROOT.parent/f"outputs/private-test-submission-adaptive-short-{int(args.short_threshold*1000):03d}.csv"
        else:
            output=ROOT.parent/"outputs/private-test-submission-adaptive.csv"
    else:
        scores=ProbabilityBlend((cpu,bert),(.55,.45)).predict_proba(texts)
        output=ROOT.parent/"outputs/private-test-submission-scope.csv" if args.scope else OUTPUT
    if args.output is not None:
        output=args.output
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["testcase","microcats","descriptions"])
        writer.writeheader()
        for i,(case,source,text,row) in enumerate(zip(data.testcase,data.description,texts,scores)):
            threshold=args.short_threshold if args.adaptive and token_lengths[i]<=512 else .525
            cats=[c for c,s in zip(IDS,row) if s>=threshold and not explicitly_negated(text,c)]
            writer.writerow({"testcase":case,"microcats":json.dumps(cats,ensure_ascii=False),
                             "descriptions":json.dumps([excerpt(source,c) for c in cats],ensure_ascii=False)})
    with output.open("r",encoding="utf-8-sig",newline="") as f:
        saved=list(csv.DictReader(f))
    assert len(saved)==len(data)
    for case,row in zip(data.testcase,saved):
        assert row["testcase"]==case
        cats=json.loads(row["microcats"]);descs=json.loads(row["descriptions"])
        assert len(cats)==len(descs) and len(cats)==len(set(cats))
        assert all(c in IDS for c in cats) and all(isinstance(x,str) and x for x in descs)
    print(json.dumps({"file":str(output),"rows":len(saved),"bytes":output.stat().st_size,
      "empty":sum(not json.loads(r["microcats"]) for r in saved),
      "category_assignments":sum(len(json.loads(r["microcats"])) for r in saved)},ensure_ascii=False))

if __name__=="__main__":main()
