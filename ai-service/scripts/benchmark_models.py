"""Repeated near-duplicate-grouped benchmark for CPU text classifiers."""
import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, precision_score, recall_score, average_precision_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.multiclass import OneVsRestClassifier
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
IDS = (102, 103, 104, 105, 106)
SEEDS = (42, 7, 21, 101, 2026)
FIXED_THRESHOLD = 0.45


def norm(text):
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()


def load_rows():
    raw = [json.loads(s) for s in (ROOT / "data/public-train-annotated.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    by_text = {}
    for row in raw:
        by_text.setdefault(norm(row["description"]), row)
    texts = list(by_text)
    labels = np.asarray([[int(c in {int(x["mcId"]) for x in by_text[t].get("found_microcategories", [])}) for c in IDS] for t in texts], dtype=np.uint8)
    return raw, texts, labels


def vectorizer(name):
    if name == "char_35":
        return TfidfVectorizer(analyzer="char", ngram_range=(3, 5), max_features=150000, sublinear_tf=True)
    if name == "char_26":
        return TfidfVectorizer(analyzer="char", ngram_range=(2, 6), max_features=200000, sublinear_tf=True)
    if name == "charwb_35":
        return TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=150000, sublinear_tf=True)
    if name == "word_12":
        return TfidfVectorizer(ngram_range=(1, 2), max_features=100000, sublinear_tf=True)
    if name == "word_char":
        return FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), max_features=80000, sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char", ngram_range=(3, 5), max_features=120000, sublinear_tf=True)),
        ])
    raise ValueError(name)


def main():
    raw, texts, labels = load_rows()
    # The graph construction and split recipe match the project's prior audit.
    near = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(near).radius_neighbors_graph(near, mode="connectivity")
    n_components, groups = connected_components(graph, directed=False)
    variants = [
        ("char_35_C1_bal", "char_35", 1, "balanced"),
        ("char_35_C4_bal", "char_35", 4, "balanced"),
        ("char_35_C4_none", "char_35", 4, None),
        ("char_26_C4_bal", "char_26", 4, "balanced"),
        ("charwb_35_C4_bal", "charwb_35", 4, "balanced"),
        ("word_12_C4_bal", "word_12", 4, "balanced"),
        ("word_char_C4_bal", "word_char", 4, "balanced"),
    ]
    reports = []
    for seed in SEEDS:
        train, val = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(texts, labels, groups))
        y_train, y_val = labels[train], labels[val]
        feature_cache = {}
        for vector in sorted({v[1] for v in variants}):
            start = time.perf_counter()
            vec = vectorizer(vector)
            x_train = vec.fit_transform([texts[i] for i in train])
            x_val = vec.transform([texts[i] for i in val])
            feature_cache[vector] = (x_train, x_val, time.perf_counter() - start)
        for name, vector, c_value, class_weight in variants:
            start = time.perf_counter()
            x_train, x_val, vec_seconds = feature_cache[vector]
            model = OneVsRestClassifier(LogisticRegression(C=c_value, max_iter=400, class_weight=class_weight, random_state=seed, solver="liblinear"))
            model.fit(x_train, y_train)
            scores = model.predict_proba(x_val)
            pred = (scores >= FIXED_THRESHOLD).astype(np.uint8)
            reports.append({
                "seed": seed, "model": name, "micro_f1_at_0_45": float(f1_score(y_val, pred, average="micro", zero_division=0)),
                "macro_f1_at_0_45": float(f1_score(y_val, pred, average="macro", zero_division=0)),
                "precision_micro_at_0_45": float(precision_score(y_val, pred, average="micro", zero_division=0)),
                "recall_micro_at_0_45": float(recall_score(y_val, pred, average="micro", zero_division=0)),
                "mean_average_precision": float(average_precision_score(y_val, scores, average="macro")),
                "fit_predict_seconds": round(time.perf_counter() - start, 2), "vectorize_seconds": round(vec_seconds, 2),
            })
            print(json.dumps(reports[-1]), flush=True)
    summary = []
    for name in [v[0] for v in variants]:
        subset = [r for r in reports if r["model"] == name]
        summary.append({"model": name, **{k: float(np.mean([r[k] for r in subset])) for k in ("micro_f1_at_0_45", "macro_f1_at_0_45", "precision_micro_at_0_45", "recall_micro_at_0_45", "mean_average_precision")}, "micro_f1_std": float(np.std([r["micro_f1_at_0_45"] for r in subset])), "folds": len(subset)})
    normalized_data_bytes = (ROOT / "data/public-train-annotated.jsonl").read_bytes().replace(b"\r\n", b"\n")
    report = {
        "dataset_sha256_lf_normalized": hashlib.sha256(normalized_data_bytes).hexdigest(),
        "source_rows": len(raw), "unique_descriptions": len(texts), "label_quality": "organizer weak labels, not human gold",
        "split": "5 repeated 80/20 GroupShuffleSplit folds on connected components of char TF-IDF cosine >= 0.95",
        "near_duplicate_threshold": 0.95, "near_duplicate_components": int(n_components), "seeds": SEEDS,
        "fixed_threshold": FIXED_THRESHOLD, "variants": reports, "summary": sorted(summary, key=lambda x: x["micro_f1_at_0_45"], reverse=True),
    }
    out = ROOT / "work" / "benchmark_models.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(out), "summary": report["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
