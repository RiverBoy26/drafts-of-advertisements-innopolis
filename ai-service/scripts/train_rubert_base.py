"""Train the optional local RuBERT model on all deduplicated organizer examples."""
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
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
LEARNING_RATE = 2e-5


class Rows(Dataset):
    def __init__(self, encodings, labels):
        self.encodings, self.labels = encodings, labels

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, i):
        row = {key: values[i] for key, values in self.encodings.items()}
        row["labels"] = torch.tensor(self.labels[i], dtype=torch.float32)
        return row


def main():
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this Python environment")
    torch.set_num_threads(4)
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    _, texts, labels = load_rows()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    encoded = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)

    def collate(batch):
        target = torch.stack([item.pop("labels") for item in batch])
        result = tokenizer.pad(batch, padding=True, return_tensors="pt")
        result["labels"] = target
        return result

    loader = DataLoader(Rows(encoded, labels), batch_size=BATCH, shuffle=True,
                        collate_fn=collate, pin_memory=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, num_labels=5, problem_type="multi_label_classification",
    ).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=.01)
    scaler = torch.amp.GradScaler("cuda")
    started = time.perf_counter()
    reports = []
    for epoch in range(EPOCHS):
        model.train()
        losses = []
        optimizer.zero_grad(set_to_none=True)
        for step, batch in enumerate(loader, 1):
            batch = {key: value.cuda(non_blocking=True) for key, value in batch.items()}
            with torch.amp.autocast("cuda", dtype=torch.float16):
                loss = model(**batch).loss / ACCUMULATION
            scaler.scale(loss).backward()
            if step % ACCUMULATION == 0 or step == len(loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            losses.append(float(loss.detach()) * ACCUMULATION)
        row = {"epoch": epoch + 1, "mean_train_loss": float(np.mean(losses)),
               "elapsed_seconds": round(time.perf_counter() - started, 2),
               "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1)}
        reports.append(row)
        print(json.dumps(row), flush=True)

    output = ROOT / "artifacts/rubert_base"
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    print(json.dumps({"model_id": MODEL_ID, "seed": SEED, "rows": len(texts),
                      "class_ids": [102, 103, 104, 105, 106], "threshold": .475,
                      "max_length": MAX_LENGTH, "epochs": EPOCHS, "reports": reports,
                      "artifact": str(output.relative_to(ROOT))}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
