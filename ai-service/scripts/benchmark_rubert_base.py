"""Five-fold grouped fine-tuning benchmark for Russian RuBERT-base."""
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from benchmark_models import SEEDS, load_rows

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "DeepPavlov/rubert-base-cased"
MAX_LENGTH = 512
BATCH = 4
ACCUMULATION = 2
EPOCHS = 3
LEARNING_RATE = 2e-5


class Rows(Dataset):
    def __init__(self, encodings, labels=None):
        self.encodings, self.labels = encodings, labels

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, i):
        row = {key: values[i] for key, values in self.encodings.items()}
        if self.labels is not None:
            row["labels"] = torch.tensor(self.labels[i], dtype=torch.float32)
        return row


def main():
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this Python environment")
    raw, texts, labels = load_rows()
    if len(texts) != 4854:
        raise RuntimeError(f"Expected 4854 deduplicated texts, got {len(texts)}")
    split_predictions = json.loads(np.load(ROOT / "work/c_sweep_predictions.npz")["payload"].item())
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    encoded = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)

    def collate(batch):
        y_batch = torch.stack([row.pop("labels") for row in batch]) if "labels" in batch[0] else None
        out = tokenizer.pad(batch, padding=True, return_tensors="pt")
        if y_batch is not None:
            out["labels"] = y_batch
        return out

    reports, saved = [], {}
    for seed in SEEDS:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        val = split_predictions[f"{seed}|charwb35_C50"]["indices"]
        val_set = set(val)
        train = [i for i in range(len(texts)) if i not in val_set]
        train_enc = {key: [values[i] for i in train] for key, values in encoded.items()}
        val_enc = {key: [values[i] for i in val] for key, values in encoded.items()}
        train_loader = DataLoader(Rows(train_enc, labels[train]), batch_size=BATCH, shuffle=True, collate_fn=collate, pin_memory=True)
        val_loader = DataLoader(Rows(val_enc, labels[val]), batch_size=8, shuffle=False, collate_fn=collate, pin_memory=True)
        torch.cuda.reset_peak_memory_stats()
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_ID, num_labels=5, problem_type="multi_label_classification",
        ).cuda()
        optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=.01)
        scaler = torch.amp.GradScaler("cuda")
        started = time.perf_counter()
        epoch_reports = []
        seed_scores = {}
        for epoch in range(EPOCHS):
            model.train()
            losses = []
            optimizer.zero_grad(set_to_none=True)
            for step, batch in enumerate(train_loader, 1):
                batch = {k: v.cuda(non_blocking=True) for k, v in batch.items()}
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    loss = model(**batch).loss / ACCUMULATION
                scaler.scale(loss).backward()
                if step % ACCUMULATION == 0 or step == len(train_loader):
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                losses.append(float(loss.detach()) * ACCUMULATION)
            model.eval()
            pred = []
            with torch.inference_mode():
                for batch in val_loader:
                    batch = {k: v.cuda(non_blocking=True) for k, v in batch.items() if k != "labels"}
                    with torch.amp.autocast("cuda", dtype=torch.float16):
                        logits = model(**batch).logits
                    pred.append(torch.sigmoid(logits.float()).cpu().numpy())
            scores = np.concatenate(pred)
            y_val = labels[val].astype(np.uint8)
            row = {
                "seed": seed, "epoch": epoch + 1,
                "micro_f1_at_0_45": float(f1_score(y_val, scores >= .45, average="micro", zero_division=0)),
                "micro_f1_at_0_50": float(f1_score(y_val, scores >= .50, average="micro", zero_division=0)),
                "precision_micro_at_0_45": float(precision_score(y_val, scores >= .45, average="micro", zero_division=0)),
                "recall_micro_at_0_45": float(recall_score(y_val, scores >= .45, average="micro", zero_division=0)),
                "macro_f1_at_0_45": float(f1_score(y_val, scores >= .45, average="macro", zero_division=0)),
                "mean_average_precision": float(average_precision_score(y_val, scores, average="macro")),
                "mean_train_loss": float(np.mean(losses)), "elapsed_seconds": round(time.perf_counter() - started, 2),
                "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            }
            epoch_reports.append(row)
            seed_scores[str(epoch + 1)] = scores.tolist()
            print(json.dumps(row), flush=True)
        reports.append({"seed": seed, "train_rows": len(train), "validation_rows": len(val), "epochs": epoch_reports})
        saved[str(seed)] = {"val_indices": val, "y": labels[val].astype(int).tolist(), "scores_by_epoch": seed_scores}
        del model, optimizer, scaler, train_loader, val_loader
        torch.cuda.empty_cache()
    normalized = (ROOT / "data/public-train-annotated.jsonl").read_bytes().replace(b"\r\n", b"\n")
    result = {
        "model_id": MODEL_ID, "max_length": MAX_LENGTH, "batch_size": BATCH,
        "gradient_accumulation": ACCUMULATION, "effective_batch_size": BATCH * ACCUMULATION,
        "epochs": EPOCHS, "learning_rate": LEARNING_RATE, "class_ids": [102, 103, 104, 105, 106],
        "dataset_sha256_lf_normalized": hashlib.sha256(normalized).hexdigest(),
        "source_rows": len(raw), "unique_descriptions": len(texts), "weak_labels_not_gold": True,
        "split": "same five repeated 80/20 GroupShuffleSplit folds on connected near-duplicate components (cosine >= 0.95)",
        "gpu": torch.cuda.get_device_name(0), "reports": reports,
    }
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (work / "benchmark_rubert_base.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(work / "rubert_base_predictions.npz", payload=json.dumps(saved))
    summaries = []
    for epoch in range(1, EPOCHS + 1):
        rows = [r["epochs"][epoch - 1] for r in reports]
        summaries.append({"epoch": epoch, **{key: float(np.mean([row[key] for row in rows])) for key in ("micro_f1_at_0_45", "micro_f1_at_0_50", "macro_f1_at_0_45", "precision_micro_at_0_45", "recall_micro_at_0_45", "mean_average_precision", "elapsed_seconds")}, "micro_f1_std_at_0_45": float(np.std([row["micro_f1_at_0_45"] for row in rows]))})
    print(json.dumps({"saved": "work/benchmark_rubert_base.json", "summary": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
