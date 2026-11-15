"""Evaluate the refreshed weights on independent local sets and write submission CSV."""
import argparse, csv, json, sys
from pathlib import Path
import joblib, numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_user_updated_cpu import IDS, norm
from train_conflict_resolved_candidate import evaluate, read_jsonl
from app.main import explicitly_negated
from app.transformer_classifier import RuBertClassifier
from make_private_submission import excerpt

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-csv", type=Path, required=True, help="Path to the private input CSV; the file is not stored in this repository")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "outputs/private-test-submission-conflict-resolved.csv")
    args = parser.parse_args()
    base = read_jsonl(ROOT / "data/user-updated-train-conflict-resolved-base.jsonl")
    added = read_jsonl(ROOT / "data/manual-conflict-resolved-additions.jsonl")
    base_text = {norm(r["description"]) for r in base}
    added_text = {norm(r["description"]) for r in added}
    reference = json.loads((ROOT / "data/manual_reference_from_xlsx.json").read_text(encoding="utf-8"))
    manual = [dict(source="manual-reference", id=r["id"], description=r["description"], labels=r["labels"])
              for r in reference if norm(r["description"]) not in base_text | added_text]
    if len(manual) != 19: raise RuntimeError(f"Expected 19 independent reference rows, got {len(manual)}")
    ood = read_jsonl(ROOT / "data/user-updated-ood.jsonl")
    old = evaluate(joblib.load(ROOT / "artifacts/cpu_char_intent_context.joblib")["model"],
                   ROOT / "artifacts/rubert_intent_context", manual, ood)
    new_cpu = joblib.load(ROOT / "artifacts/cpu_char_conflict_resolved.joblib")["model"]
    new = evaluate(new_cpu, ROOT / "artifacts/rubert_conflict_resolved", manual, ood)

    source = args.private_csv
    data = pd.read_csv(source, dtype=str, keep_default_na=False)
    if list(data.columns) != ["testcase", "description"] or data.testcase.duplicated().any():
        raise RuntimeError("Private CSV schema or case IDs are invalid")
    texts = [norm(s) for s in data.description]
    cpu_scores = new_cpu.predict_proba(texts)
    bert = RuBertClassifier(str(ROOT / "artifacts/rubert_conflict_resolved"))
    bert_scores = bert.predict_proba(texts)
    lengths = [len(ids) for ids in bert.tokenizer(texts, add_special_tokens=True, truncation=False)["input_ids"]]
    weights = np.asarray([.55 if n <= 512 else .45 for n in lengths], dtype=np.float32)[:, None]
    scores = (1 - weights) * cpu_scores + weights * bert_scores
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["testcase", "microcats", "descriptions"]); writer.writeheader()
        for case, source_text, text, row in zip(data.testcase, data.description, texts, scores):
            cats = [c for c, score in zip(IDS, row) if score >= .525 and not explicitly_negated(text, c)]
            writer.writerow({"testcase": case, "microcats": json.dumps(cats),
                             "descriptions": json.dumps([excerpt(source_text, c) for c in cats], ensure_ascii=False)})
    with output.open("r", encoding="utf-8-sig", newline="") as f: rows = list(csv.DictReader(f))
    assert len(rows) == len(data) and [r["testcase"] for r in rows] == list(data.testcase)
    for row in rows:
        cats=json.loads(row["microcats"]); desc=json.loads(row["descriptions"])
        assert all(c in IDS for c in cats) and len(cats)==len(desc) and len(cats)==len(set(cats))
    report = {"previous_intent_context": old, "candidate_conflict_resolved": new,
              "submission": {"file": str(output), "rows": len(rows), "bytes": output.stat().st_size,
                             "empty_predictions": sum(not json.loads(r["microcats"]) for r in rows),
                             "category_assignments": sum(len(json.loads(r["microcats"])) for r in rows),
                             "parse_validation": "passed", "secret_score": None},
              "config": {"cpu_weight_short": .45, "rubert_weight_short": .55,
                         "cpu_weight_long": .55, "rubert_weight_long": .45,
                         "short_limit_tokens": 512, "threshold": .525}}
    path=ROOT/"work/conflict_resolved_candidate_eval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"previous_manual":old["manual_unseen"],"candidate_manual":new["manual_unseen"],
                      "previous_ood":old["ood"],"candidate_ood":new["ood"],"submission":report["submission"]},
                     ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
