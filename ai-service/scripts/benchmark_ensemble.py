"""Compare RuBERT, the selected CPU model, and simple score blends on identical folds."""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, average_precision_score

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (42, 7, 21, 101, 2026)
THRESHOLDS = (.40, .425, .45, .475, .50, .525)
WEIGHTS = (0.0, .25, .5, .75, 1.0)  # weight assigned to RuBERT probabilities


def main():
    bert = json.loads(np.load(ROOT / "work/rubert_base_predictions.npz")["payload"].item())
    cpu = json.loads(np.load(ROOT / "work/vocab_c200_predictions.npz")["payload"].item())
    reports = []
    for seed in SEEDS:
        b = bert[str(seed)]
        c = cpu[f"{seed}|cap350k_min2_sublinear"]
        if b["val_indices"] != c["indices"] or b["y"] != c["y"]:
            raise RuntimeError(f"validation mismatch for seed {seed}")
        y = np.asarray(b["y"], dtype=np.uint8)
        scores = {0.0: np.asarray(c["scores"]), 1.0: np.asarray(b["scores_by_epoch"]["3"])}
        for weight in (.25, .5, .75):
            scores[weight] = (1 - weight) * scores[0.0] + weight * scores[1.0]
        for weight, values in scores.items():
            for threshold in THRESHOLDS:
                pred = values >= threshold
                reports.append({
                    "seed": seed, "rubert_weight": weight, "threshold": threshold,
                    "micro_f1": float(f1_score(y, pred, average="micro", zero_division=0)),
                    "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
                    "precision_micro": float(precision_score(y, pred, average="micro", zero_division=0)),
                    "recall_micro": float(recall_score(y, pred, average="micro", zero_division=0)),
                    "mean_average_precision": float(average_precision_score(y, values, average="macro")),
                })
    summary = []
    for weight in WEIGHTS:
        for threshold in THRESHOLDS:
            rows = [r for r in reports if r["rubert_weight"] == weight and r["threshold"] == threshold]
            summary.append({"rubert_weight": weight, "threshold": threshold,
                            **{key: float(np.mean([r[key] for r in rows])) for key in (
                                "micro_f1", "macro_f1", "precision_micro", "recall_micro", "mean_average_precision")},
                            "micro_f1_std": float(np.std([r["micro_f1"] for r in rows]))})
    result = {"folds": len(SEEDS), "same_validation_indices": True, "reports": reports,
              "summary": sorted(summary, key=lambda x: x["micro_f1"], reverse=True)}
    (ROOT / "work/benchmark_ensemble.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"best_by_f1": result["summary"][:12],
                      "best_blend_by_weight": [max((r for r in summary if r["rubert_weight"] == weight), key=lambda x: x["micro_f1"]) for weight in WEIGHTS]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
