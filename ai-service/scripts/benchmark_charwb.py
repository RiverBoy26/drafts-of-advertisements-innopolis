"""Near-duplicate-grouped tuning around the strongest char_wb candidate."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.multiclass import OneVsRestClassifier
from sklearn.neighbors import NearestNeighbors

from benchmark_models import IDS, SEEDS, load_rows

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = .45


def main():
    raw, texts, y = load_rows()
    near = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(near).radius_neighbors_graph(near, mode="connectivity")
    n_components, groups = connected_components(graph, directed=False)
    specs = [
        ("charwb35_C1_bal_liblinear", (3, 5), 1, "balanced", "liblinear"),
        ("charwb35_C4_bal_liblinear", (3, 5), 4, "balanced", "liblinear"),
        ("charwb35_C10_bal_liblinear", (3, 5), 10, "balanced", "liblinear"),
        ("charwb26_C4_bal_liblinear", (2, 6), 4, "balanced", "liblinear"),
        ("charwb35_C4_bal_lbfgs", (3, 5), 4, "balanced", "lbfgs"),
        ("charwb26_C4_bal_lbfgs", (2, 6), 4, "balanced", "lbfgs"),
    ]
    reports, predictions = [], {}
    for seed in SEEDS:
        tr, va = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(texts, y, groups))
        matrices = {}
        for ngram in sorted({s[1] for s in specs}):
            feature_cap = 150000 if ngram == (3, 5) else 200000
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram, max_features=feature_cap, sublinear_tf=True)
            start = time.perf_counter()
            a = vec.fit_transform([texts[i] for i in tr])
            b = vec.transform([texts[i] for i in va])
            matrices[ngram] = (a, b, time.perf_counter() - start)
        for name, ngram, c_value, class_weight, solver in specs:
            a, b, vector_seconds = matrices[ngram]
            model = OneVsRestClassifier(LogisticRegression(C=c_value, max_iter=400, class_weight=class_weight, random_state=seed, solver=solver))
            start = time.perf_counter()
            model.fit(a, y[tr])
            scores = model.predict_proba(b)
            pred = scores >= THRESHOLD
            report = {
                "seed": seed, "model": name, "micro_f1_at_0_45": float(f1_score(y[va], pred, average="micro", zero_division=0)),
                "macro_f1_at_0_45": float(f1_score(y[va], pred, average="macro", zero_division=0)),
                "precision_micro_at_0_45": float(precision_score(y[va], pred, average="micro", zero_division=0)),
                "recall_micro_at_0_45": float(recall_score(y[va], pred, average="micro", zero_division=0)),
                "mean_average_precision": float(average_precision_score(y[va], scores, average="macro")),
                "fit_predict_seconds": round(time.perf_counter() - start, 2), "vectorize_seconds": round(vector_seconds, 2),
            }
            reports.append(report)
            predictions[f"{seed}|{name}"] = {"indices": va.tolist(), "y": y[va].astype(int).tolist(), "scores": scores.tolist()}
            print(json.dumps(report), flush=True)
    summary = []
    for name, *_ in specs:
        rows = [r for r in reports if r["model"] == name]
        summary.append({
            "model": name,
            **{k: float(np.mean([r[k] for r in rows])) for k in (
                "micro_f1_at_0_45", "macro_f1_at_0_45", "precision_micro_at_0_45",
                "recall_micro_at_0_45", "mean_average_precision",
            )},
            "micro_f1_std": float(np.std([r["micro_f1_at_0_45"] for r in rows])),
        })
    payload = {"source_rows": len(raw), "unique_descriptions": len(texts), "near_duplicate_components": int(n_components), "threshold": THRESHOLD, "seeds": SEEDS, "reports": reports, "summary": sorted(summary, key=lambda x: x["micro_f1_at_0_45"], reverse=True)}
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (work / "benchmark_charwb.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(work / "charwb_predictions.npz", payload=json.dumps(predictions))
    print(json.dumps({"saved": "work/benchmark_charwb.json", "summary": payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
