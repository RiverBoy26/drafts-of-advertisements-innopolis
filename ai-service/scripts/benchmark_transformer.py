"""Optional GPU fine-tuning benchmark; run with the user's CUDA-enabled Python."""
import hashlib
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import torch
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "cointegrated/rubert-tiny2"
IDS = (102, 103, 104, 105, 106)
SEEDS = (42, 7, 21, 101, 2026)
MAX_LENGTH = 512
EPOCHS = 3
BATCH = 8


def norm(text):
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()


def load_data():
    raw = [json.loads(s) for s in (ROOT / "data/public-train-annotated.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    by_text = {}
    for row in raw:
        by_text.setdefault(norm(row["description"]), row)
    texts = list(by_text)
    labels = np.asarray([[int(c in {int(x["mcId"]) for x in by_text[t].get("found_microcategories", [])}) for c in IDS] for t in texts], dtype=np.float32)
    return raw, texts, labels


class Rows(Dataset):
    def __init__(self, encodings, labels=None):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.encodings.items()}
        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[i], dtype=torch.float32)
        return item


def main():
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this Python environment")
    device = torch.device("cuda")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    raw, texts, labels = load_data()
    graph_x = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(graph_x).radius_neighbors_graph(graph_x, mode="connectivity")
    n_components, groups = connected_components(graph, directed=False)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    encoded = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)
    def collate(batch):
        labels_batch = torch.stack([item.pop("labels") for item in batch]) if "labels" in batch[0] else None
        result = tokenizer.pad(batch, padding=True, return_tensors="pt")
        if labels_batch is not None:
            result["labels"] = labels_batch
        return result
    reports = []
    saved = {}
    for seed in SEEDS:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        train, val = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(texts, labels, groups))
        train_enc = {k: [v[i] for i in train] for k, v in encoded.items()}
        val_enc = {k: [v[i] for i in val] for k, v in encoded.items()}
        train_loader = DataLoader(Rows(train_enc, labels[train]), batch_size=BATCH, shuffle=True, collate_fn=collate, pin_memory=True)
        val_loader = DataLoader(Rows(val_enc, labels[val]), batch_size=16, shuffle=False, collate_fn=collate, pin_memory=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_ID, num_labels=len(IDS), problem_type="multi_label_classification",
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-5, weight_decay=.01)
        scaler = torch.amp.GradScaler("cuda")
        started = time.perf_counter()
        epoch_loss = []
        for epoch in range(EPOCHS):
            model.train()
            loss_sum = 0.0
            for batch in train_loader:
                batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
                optimizer.zero_grad(set_to_none=True)
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    result = model(**batch)
                    loss = result.loss
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                loss_sum += float(loss.detach())
            epoch_loss.append(loss_sum / max(1, len(train_loader)))
        model.eval()
        chunks = []
        with torch.inference_mode():
            for batch in val_loader:
                batch = {k: v.to(device, non_blocking=True) for k, v in batch.items() if k != "labels"}
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    logits = model(**batch).logits
                chunks.append(torch.sigmoid(logits.float()).cpu().numpy())
        scores = np.concatenate(chunks)
        y = labels[val].astype(np.uint8)
        row = {
            "seed": seed, "micro_f1_at_0_45": float(f1_score(y, scores >= .45, average="micro", zero_division=0)),
            "micro_f1_at_0_50": float(f1_score(y, scores >= .50, average="micro", zero_division=0)),
            "precision_micro_at_0_45": float(precision_score(y, scores >= .45, average="micro", zero_division=0)),
            "recall_micro_at_0_45": float(recall_score(y, scores >= .45, average="micro", zero_division=0)),
            "macro_f1_at_0_45": float(f1_score(y, scores >= .45, average="macro", zero_division=0)),
            "mean_average_precision": float(average_precision_score(y, scores, average="macro")),
            "val_rows": len(val), "epoch_train_loss": epoch_loss, "fit_predict_seconds": round(time.perf_counter() - started, 2),
            "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        }
        reports.append(row)
        saved[str(seed)] = {"val_indices": val.tolist(), "y": y.tolist(), "scores": scores.tolist()}
        print(json.dumps(row), flush=True)
        del model, optimizer, scaler
        torch.cuda.empty_cache()
    normalized_data = (ROOT / "data/public-train-annotated.jsonl").read_bytes().replace(b"\r\n", b"\n")
    summary = {
        "model_id": MODEL_ID, "max_length": MAX_LENGTH, "epochs": EPOCHS, "batch_size": BATCH,
        "learning_rate": 3e-5, "class_ids": IDS, "weak_labels_not_gold": True,
        "dataset_sha256_lf_normalized": hashlib.sha256(normalized_data).hexdigest(),
        "unique_descriptions": len(texts), "source_rows": len(raw), "near_duplicate_components": int(n_components),
        "split": "GroupShuffleSplit 80/20 over connected components of char TF-IDF cosine >= 0.95",
        "seeds": SEEDS, "gpu": torch.cuda.get_device_name(0), "metrics": reports,
    }
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (work / "benchmark_transformer.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(work / "transformer_predictions.npz", payload=json.dumps(saved))
    print(json.dumps({"saved": "work/benchmark_transformer.json", "summary": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
