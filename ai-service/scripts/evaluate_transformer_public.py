"""Run the transformer-backed service classifier on the already-inspected public set."""
import json
import statistics
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

import app.main as service

ROOT = Path(__file__).resolve().parents[1]
IDS = (102, 103, 104, 105, 106)
PREFIXES = {"stukaturn": 102, "plitocn": 103, "santehn": 104,
            "elektrika": 105, "pokleika oboev": 106}


def target_ids(labels):
    result = set()
    for label in labels:
        normalized = service.latin(service.norm(str(label)))
        for prefix, mc_id in PREFIXES.items():
            if normalized.startswith(prefix):
                result.add(mc_id)
    return result


def main():
    if not service.ACTIVE_BACKEND.startswith(("ensemble-cuda", "rubert-cuda")):
        raise SystemExit(f"Expected CUDA transformer backend, got {service.ACTIVE_BACKEND}")
    data = pd.read_parquet(ROOT / "data/public-test-dataset.parquet")
    truth = np.asarray([[int(mc in target_ids(labels)) for mc in IDS] for labels in data.categories], dtype=np.uint8)
    train_texts = {
        service.norm(json.loads(line)["description"])
        for line in (ROOT / "data/public-train-annotated.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    predicted, latencies = [], []
    for text in data.description:
        started = time.perf_counter()
        targets = service.predict(str(text), 101)
        latencies.append((time.perf_counter() - started) * 1000)
        predicted.append([int(mc in targets) for mc in IDS])
    predicted = np.asarray(predicted, dtype=np.uint8)
    report = {
        "dataset": "organizer public-test-dataset.parquet",
        "backend": service.ACTIVE_BACKEND,
        "threshold": service.MODEL["threshold"],
        "source_mcId": 101,
        "source_mcId_note": "assumption: parquet has no source mcId column",
        "rows": len(data), "unique_normalized_descriptions": len({service.norm(str(x)) for x in data.description}),
        "exact_overlap_rows_with_train": sum(service.norm(str(x)) in train_texts for x in data.description),
        "micro_f1": float(f1_score(truth, predicted, average="micro", zero_division=0)),
        "precision_micro": float(precision_score(truth, predicted, average="micro", zero_division=0)),
        "recall_micro": float(recall_score(truth, predicted, average="micro", zero_division=0)),
        "per_class_f1": {str(mc): float(f1_score(truth[:, i], predicted[:, i], zero_division=0)) for i, mc in enumerate(IDS)},
        "latency_ms": {"p50": statistics.median(latencies), "p95": sorted(latencies)[int(.95 * (len(latencies) - 1))]},
        "note": "Transparent public diagnostic only; the set was inspected and was not used to choose the model or threshold.",
    }
    (ROOT / "work/evaluate_transformer_public.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
