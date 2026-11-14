"""Train a separate CPU candidate with 64 synthetic all-negative descriptions."""
import json
import argparse
import numpy as np
import joblib
from benchmark_noise_robustness import ROOT, IDS, norm
from benchmark_noise_training import make_model

parser = argparse.ArgumentParser(); parser.add_argument('--count', type=int, default=64); count = parser.parse_args().count
rows = [json.loads(line) for line in (ROOT / "data" / f"public-train-annotated-noise{count}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
dedup = {}
for row in rows:
    dedup.setdefault(norm(row["description"]), row)
texts = list(dedup)
labels = np.asarray([[int(c in {int(x["mcId"]) for x in row.get("found_microcategories", [])}) for c in IDS]
                     for row in dedup.values()], dtype=np.uint8)
negative_count = sum(bool(row.get("synthetic_negative")) for row in dedup.values())
model = make_model(42)
model.fit(texts, labels)
output = ROOT / "artifacts" / f"cpu_char_noise{count}.joblib"
joblib.dump({"model": model, "class_ids": IDS, "input_field": "description", "threshold": 0.45,
             "version": f"tfidf-charwb-35-c200-min2-noise{count}-v1", "noise_training_rows": negative_count,
             "note": "candidate only; synthetic negative samples; original labels unchanged; source mcId=101"}, output, compress=3)
print(json.dumps({"artifact": str(output), "fit_rows": len(texts), "synthetic_negatives": negative_count}, ensure_ascii=False))
