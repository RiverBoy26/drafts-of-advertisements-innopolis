"""Probe whether reducing TF-IDF regularization beyond C=50 generalizes."""
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

from benchmark_models import SEEDS, load_rows

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [("C50", 50), ("C100", 100), ("C200", 200), ("C500", 500)]
THRESHOLD = .45


def main():
    raw, texts, y = load_rows()
    near = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(near).radius_neighbors_graph(near, mode="connectivity")
    n_components, groups = connected_components(graph, directed=False)
    reports, predictions = [], {}
    for seed in SEEDS:
        train, val = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(texts, y, groups))
        vector = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=150000, sublinear_tf=True)
        vector_started = time.perf_counter()
        x_train = vector.fit_transform([texts[i] for i in train])
        x_val = vector.transform([texts[i] for i in val])
        vector_seconds = time.perf_counter() - vector_started
        for name, c_value in CONFIGS:
            model = OneVsRestClassifier(LogisticRegression(C=c_value, max_iter=800, class_weight="balanced", random_state=seed, solver="liblinear"))
            started = time.perf_counter()
            model.fit(x_train, y[train])
            scores = model.predict_proba(x_val)
            pred = scores >= THRESHOLD
            row = {
                "seed": seed, "model": name, "micro_f1_at_0_45": float(f1_score(y[val], pred, average="micro", zero_division=0)),
                "macro_f1_at_0_45": float(f1_score(y[val], pred, average="macro", zero_division=0)),
                "precision_micro_at_0_45": float(precision_score(y[val], pred, average="micro", zero_division=0)),
                "recall_micro_at_0_45": float(recall_score(y[val], pred, average="micro", zero_division=0)),
                "mean_average_precision": float(average_precision_score(y[val], scores, average="macro")),
                "fit_predict_seconds": round(time.perf_counter() - started, 2), "vectorize_seconds": round(vector_seconds, 2),
            }
            reports.append(row)
            predictions[f"{seed}|{name}"] = {"indices": val.tolist(), "y": y[val].astype(int).tolist(), "scores": scores.tolist()}
            print(json.dumps(row), flush=True)
    summaries = []
    for name, _ in CONFIGS:
        subset = [row for row in reports if row["model"] == name]
        summaries.append({"model": name, **{k: float(np.mean([r[k] for r in subset])) for k in ("micro_f1_at_0_45", "macro_f1_at_0_45", "precision_micro_at_0_45", "recall_micro_at_0_45", "mean_average_precision")}, "micro_f1_std": float(np.std([r["micro_f1_at_0_45"] for r in subset]))})
    output = {"source_rows": len(raw), "unique_descriptions": len(texts), "near_duplicate_components": int(n_components), "threshold": THRESHOLD, "seeds": SEEDS, "reports": reports, "summary": sorted(summaries, key=lambda x: x["micro_f1_at_0_45"], reverse=True)}
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (work / "benchmark_high_c.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(work / "high_c_predictions.npz", payload=json.dumps(predictions))
    print(json.dumps({"saved": "work/benchmark_high_c.json", "summary": output["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
