"""Check complementary linear and naive-Bayes learners on the best TF-IDF view."""
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
from sklearn.naive_bayes import ComplementNB
from sklearn.neighbors import NearestNeighbors
from sklearn.svm import LinearSVC

from benchmark_models import SEEDS, load_rows

ROOT = Path(__file__).resolve().parents[1]


def main():
    raw, texts, y = load_rows()
    near = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(near).radius_neighbors_graph(near, mode="connectivity")
    n_components, groups = connected_components(graph, directed=False)
    configs = [
        ("svm_C0.1", "svm", .1), ("svm_C1", "svm", 1),
        ("complement_nb_a0.01", "nb", .01), ("complement_nb_a0.1", "nb", .1),
    ]
    reports = []
    for seed in SEEDS:
        train, val = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(texts, y, groups))
        vector = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=150000, sublinear_tf=True)
        x_train = vector.fit_transform([texts[i] for i in train])
        x_val = vector.transform([texts[i] for i in val])
        for name, kind, parameter in configs:
            if kind == "svm":
                estimator = OneVsRestClassifier(LinearSVC(C=parameter, class_weight="balanced", max_iter=10000, dual="auto", random_state=seed))
                threshold = 0.0
            else:
                estimator = OneVsRestClassifier(ComplementNB(alpha=parameter))
                threshold = .45
            started = time.perf_counter()
            estimator.fit(x_train, y[train])
            scores = estimator.decision_function(x_val) if kind == "svm" else estimator.predict_proba(x_val)
            pred = scores >= threshold
            row = {
                "seed": seed, "model": name, "threshold": threshold,
                "micro_f1": float(f1_score(y[val], pred, average="micro", zero_division=0)),
                "macro_f1": float(f1_score(y[val], pred, average="macro", zero_division=0)),
                "precision_micro": float(precision_score(y[val], pred, average="micro", zero_division=0)),
                "recall_micro": float(recall_score(y[val], pred, average="micro", zero_division=0)),
                "mean_average_precision": float(average_precision_score(y[val], scores, average="macro")),
                "fit_predict_seconds": round(time.perf_counter() - started, 2),
            }
            reports.append(row)
            print(json.dumps(row), flush=True)
    summary = []
    for name, *_ in configs:
        subset = [r for r in reports if r["model"] == name]
        summary.append({"model": name, **{k: float(np.mean([r[k] for r in subset])) for k in ("micro_f1", "macro_f1", "precision_micro", "recall_micro", "mean_average_precision")}, "micro_f1_std": float(np.std([r["micro_f1"] for r in subset]))})
    output = {"source_rows": len(raw), "unique_descriptions": len(texts), "near_duplicate_components": int(n_components), "folds": len(SEEDS), "reports": reports, "summary": sorted(summary, key=lambda x: x["micro_f1"], reverse=True)}
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (work / "benchmark_alternatives.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": "work/benchmark_alternatives.json", "summary": output["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
