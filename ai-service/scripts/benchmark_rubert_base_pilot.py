"""One-fold pilot of Russian BERT-base against the compact TF-IDF baseline."""
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from benchmark_models import load_rows

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "DeepPavlov/rubert-base-cased"
SEED = 42
MAX_LENGTH = 512
BATCH = 4
ACCUMULATION = 2
EPOCHS = 3


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
    predictions = json.loads(np.load(ROOT / "work/charwb_predictions.npz")["payload"].item())
    val = predictions[f"{SEED}|charwb35_C10_bal_liblinear"]["indices"]
    val_set = set(val)
    train = [i for i in range(4854) if i not in val_set]
    raw, texts, labels = load_rows()
    # Guard against accidental split/data-order drift from the stored TF-IDF fold.
    if len(texts) != 4854 or len(labels[train]) == 0:
        raise RuntimeError("The stored pilot fold does not match the current deduplicated data")

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    encoded = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)

    def collate(batch):
        y_batch = torch.stack([row.pop("labels") for row in batch]) if "labels" in batch[0] else None
        out = tokenizer.pad(batch, padding=True, return_tensors="pt")
        if y_batch is not None:
            out["labels"] = y_batch
        return out

    train_enc = {key: [values[i] for i in train] for key, values in encoded.items()}
    val_enc = {key: [values[i] for i in val] for key, values in encoded.items()}
    train_loader = DataLoader(Rows(train_enc, labels[train]), batch_size=BATCH, shuffle=True, collate_fn=collate, pin_memory=True)
    val_loader = DataLoader(Rows(val_enc, labels[val]), batch_size=8, shuffle=False, collate_fn=collate, pin_memory=True)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=5, problem_type="multi_label_classification").cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=.01)
    scaler = torch.amp.GradScaler("cuda")
    epoch_reports = []
    predictions_by_epoch = {}
    started = time.perf_counter()
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
        y = labels[val].astype(np.uint8)
        row = {
            "epoch": epoch + 1, "micro_f1_at_0_45": float(f1_score(y, scores >= .45, average="micro", zero_division=0)),
            "micro_f1_at_0_50": float(f1_score(y, scores >= .50, average="micro", zero_division=0)),
            "precision_micro_at_0_45": float(precision_score(y, scores >= .45, average="micro", zero_division=0)),
            "recall_micro_at_0_45": float(recall_score(y, scores >= .45, average="micro", zero_division=0)),
            "macro_f1_at_0_45": float(f1_score(y, scores >= .45, average="macro", zero_division=0)),
            "mean_average_precision": float(average_precision_score(y, scores, average="macro")),
            "mean_train_loss": float(np.mean(losses)), "elapsed_seconds": round(time.perf_counter() - started, 2),
            "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        }
        epoch_reports.append(row)
        predictions_by_epoch[str(epoch + 1)] = scores.tolist()
        print(json.dumps(row), flush=True)
    work = ROOT / "work"
    (work / "benchmark_rubert_base_pilot.json").write_text(json.dumps({
        "model_id": MODEL_ID, "seed": SEED, "train_rows": len(train), "validation_rows": len(val),
        "max_length": MAX_LENGTH, "batch_size": BATCH, "gradient_accumulation": ACCUMULATION,
        "gpu": torch.cuda.get_device_name(0), "label_quality": "weak labels, not human-verified",
        "epochs": epoch_reports,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(work / "rubert_base_pilot_predictions.npz", payload=json.dumps({"indices": val, "y": labels[val].astype(int).tolist(), "scores_by_epoch": predictions_by_epoch}))
    print(json.dumps({"saved": "work/benchmark_rubert_base_pilot.json", "epochs": epoch_reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
