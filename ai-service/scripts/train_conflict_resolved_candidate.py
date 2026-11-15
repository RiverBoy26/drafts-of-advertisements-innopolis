"""Fit a separate updated ensemble and compare it on untouched local checks."""
from __future__ import annotations

import json, random, re, sys, time
from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from benchmark_user_updated_cpu import ROOT, IDS, make, norm
from train_human_traps_cpu import extras
from train_intent_context_candidate import supplemental
from prepare_conflict_resolved_data import label_objects


MANUAL_REPEAT = 8
HUMAN_REPEAT = 8
INTENT_REPEAT = 4
SCOPE_REPEAT = 4
SEED = 314159


def read_jsonl(path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def targets(rows):
    return np.asarray([[int(c in {int(x["mcId"]) for x in row.get("found_microcategories", [])}) for c in IDS]
                       for row in rows], dtype=np.uint8)


class EncodedData(Dataset):
    def __init__(self, encoded, labels):
        self.encoded, self.labels = encoded, labels
    def __len__(self):
        return len(self.labels)
    def __getitem__(self, i):
        return {**{k: v[i] for k, v in self.encoded.items()},
                "labels": torch.tensor(self.labels[i], dtype=torch.float32)}


def evaluate(cpu, bert_dir, manual_rows, ood_rows):
    from app.main import explicitly_negated
    from app.transformer_classifier import RuBertClassifier
    bert = RuBertClassifier(str(bert_dir))
    def predict(texts):
        texts = [norm(x) for x in texts]
        cs = cpu.predict_proba(texts)
        bs = bert.predict_proba(texts)
        token_lengths = [len(ids) for ids in bert.tokenizer(texts, add_special_tokens=True, truncation=False)["input_ids"]]
        weights = np.asarray([.55 if n <= 512 else .45 for n in token_lengths], dtype=np.float32)[:, None]
        scores = cs * (1 - weights) + bs * weights
        pred = scores >= .525
        for i, text in enumerate(texts):
            for j, c in enumerate(IDS):
                if explicitly_negated(text, c): pred[i, j] = False
        return pred, scores
    manual_texts = [r["description"] for r in manual_rows]
    y = np.asarray([[int(c in r["labels"]) for c in IDS] for r in manual_rows], dtype=np.uint8)
    mp, ms = predict(manual_texts)
    ood_texts = [r["description"] for r in ood_rows]
    op, os = predict(ood_texts)
    metrics = lambda gold, pred: {"n": len(gold), "micro_f1": float(f1_score(gold, pred, average="micro", zero_division=0)),
                                  "precision": float(precision_score(gold, pred, average="micro", zero_division=0)),
                                  "recall": float(recall_score(gold, pred, average="micro", zero_division=0)),
                                  "exact_match": float(np.all(gold == pred, axis=1).mean())}
    return {"manual_unseen": metrics(y, mp), "manual_unseen_per_class_f1": dict(zip(map(str, IDS), map(float, f1_score(y, mp, average=None, zero_division=0)))),
            "manual_cases": [{"source": r["source"], "id": r["id"], "gold": r["labels"], "predicted": [c for c, v in zip(IDS, pp) if v]}
                             for r, pp in zip(manual_rows, mp)],
            "ood": {"n": len(op), "false_positive_ads": int(op.any(axis=1).sum()), "fpr_any": float(op.any(axis=1).mean()),
                    "max_score_p95": float(np.percentile(os.max(axis=1), 95))}}


def main():
    torch.set_num_threads(4)
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    base = read_jsonl(ROOT / "data/user-updated-train-conflict-resolved-base.jsonl")
    manual = read_jsonl(ROOT / "data/manual-conflict-resolved-additions.jsonl")
    base_text = [norm(r["description"]) for r in base]
    base_y = targets(base)
    manual_text = [norm(r["description"]) for r in manual]
    manual_y = targets(manual)
    human, hy = extras()
    intent, iy = supplemental()
    scope_items = read_jsonl(ROOT / "data/offer_scope_contrasts.jsonl")
    scope = [norm(r["description"]) for r in scope_items]
    sy = targets(scope_items)
    all_text = base_text + human * HUMAN_REPEAT + intent * INTENT_REPEAT + scope * SCOPE_REPEAT + manual_text * MANUAL_REPEAT
    all_y = np.vstack((base_y, np.tile(hy, (HUMAN_REPEAT, 1)), np.tile(iy, (INTENT_REPEAT, 1)),
                       np.tile(sy, (SCOPE_REPEAT, 1)), np.tile(manual_y, (MANUAL_REPEAT, 1))))
    if not torch.cuda.is_available(): raise RuntimeError("CUDA is required for RuBERT fit")

    cpu_path = ROOT / "artifacts/cpu_char_conflict_resolved.joblib"
    cpu_path.parent.mkdir(parents=True, exist_ok=True)
    if cpu_path.exists():
        cpu = joblib.load(cpu_path)["model"]; cpu_seconds = 0.0
    else:
        cpu = make(42); start = time.perf_counter(); cpu.fit(all_text, all_y); cpu_seconds = time.perf_counter() - start
        joblib.dump({"model": cpu, "class_ids": IDS, "input_field": "description", "threshold": .525,
                     "version": "conflict-resolved-manual-v1", "base_unique_rows": len(base),
                     "corrected_weak_label_texts": 27, "manual_unique_rows": len(manual), "training_rows": len(all_text)}, cpu_path, compress=3)
    print(json.dumps({"phase": "cpu_fit_done", "seconds": round(cpu_seconds, 1), "training_rows": len(all_text)}), flush=True)

    old = ROOT / "artifacts/rubert_intent_context"
    tokenizer = AutoTokenizer.from_pretrained(old, local_files_only=True)
    # The base checkpoint already saw the full weak-label corpus and curated
    # contrast sets. Fine-tune only on the 27 adjudicated corrections plus the
    # new manual additions to finish quickly and avoid replaying noisy labels.
    original = read_jsonl(ROOT / "data/user-updated-train.jsonl")
    original_unique = {}
    for row in original: original_unique.setdefault(norm(row["description"]), row)
    resolved_map = {norm(r["description"]): r for r in base}
    correction_texts = [t for t in base_text if tuple(sorted(int(x["mcId"]) for x in original_unique[t].get("found_microcategories", []))) != tuple(sorted(int(x["mcId"]) for x in resolved_map[t].get("found_microcategories", [])))]
    corrections = [resolved_map[t] for t in correction_texts]
    correction_texts = [norm(r["description"]) for r in corrections]
    correction_y = targets(corrections)
    bert_texts = correction_texts * 8 + manual_text * MANUAL_REPEAT
    bert_y = np.vstack((np.tile(correction_y, (8, 1)), np.tile(manual_y, (MANUAL_REPEAT, 1))))
    encoded = tokenizer(bert_texts, truncation=True, max_length=512, padding=False)
    def collate(batch):
        labels = torch.stack([item.pop("labels") for item in batch])
        out = tokenizer.pad(batch, padding=True, return_tensors="pt"); out["labels"] = labels
        return out
    loader = DataLoader(EncodedData(encoded, bert_y), batch_size=4, shuffle=True, collate_fn=collate, pin_memory=True)
    model = AutoModelForSequenceClassification.from_pretrained(old, local_files_only=True).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-6, weight_decay=.01)
    scaler = torch.amp.GradScaler("cuda"); optimizer.zero_grad(set_to_none=True); start = time.perf_counter(); losses=[]
    for step, batch in enumerate(loader, 1):
        batch = {k: v.cuda(non_blocking=True) for k, v in batch.items()}
        with torch.amp.autocast("cuda", dtype=torch.float16): loss = model(**batch).loss / 2
        scaler.scale(loss).backward()
        if step % 2 == 0 or step == len(loader):
            scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
        losses.append(float(loss.detach()) * 2)
        if step % 250 == 0:
            print(json.dumps({"phase":"rubert_fit","step":step,"total":len(loader),"seconds":round(time.perf_counter()-start,1),"loss":round(float(np.mean(losses[-250:])),4)},flush=True))
    bert_path = ROOT / "artifacts/rubert_conflict_resolved"; bert_path.mkdir(exist_ok=True)
    model.save_pretrained(bert_path, safe_serialization=True); tokenizer.save_pretrained(bert_path)
    bert_seconds = time.perf_counter() - start
    del model, optimizer, scaler, loader, encoded; torch.cuda.empty_cache()
    print(json.dumps({"phase":"rubert_fit_done","seconds":round(bert_seconds,1),"mean_loss":round(float(np.mean(losses)),4),
                      "adjudicated_rows":len(corrections),"manual_rows":len(manual)},ensure_ascii=False),flush=True)

    # Compare against the previous selected weights on never-added hand labels
    # and the separate negative-only OOD file. This never reads private test.
    base_seen = set(base_text)
    old_manual = json.loads((ROOT / "data/manual_reference_from_xlsx.json").read_text(encoding="utf-8"))
    unseen = [r for r in old_manual if norm(r["description"]) not in base_seen and norm(r["description"]) not in set(manual_text)]
    assert len(unseen) == 19, f"expected 19 untouched reference rows, got {len(unseen)}"
    unseen = [{"source":"manual-reference", "id":r["id"], "description":r["description"], "labels":r["labels"]} for r in unseen]
    ood = read_jsonl(ROOT / "data/user-updated-ood.jsonl")
    old_cpu = joblib.load(ROOT / "artifacts/cpu_char_intent_context.joblib")["model"]
    old_result = evaluate(old_cpu, ROOT / "artifacts/rubert_intent_context", unseen, ood)
    new_result = evaluate(cpu, bert_path, unseen, ood)
    report = {"training": {"cpu_seconds": cpu_seconds, "rubert_seconds": bert_seconds, "mean_loss": float(np.mean(losses)),
                            "base_unique_rows": len(base), "manual_unique_rows": len(manual), "human_trap_repeats": HUMAN_REPEAT,
                            "intent_repeats": INTENT_REPEAT, "scope_repeats": SCOPE_REPEAT, "manual_repeats": MANUAL_REPEAT,
                            "rubert_finetune_rows": len(bert_texts), "adjudicated_rows": len(corrections),
                            "ruBERT_note": "Fine-tuning uses max_length=512; inference still evaluates every overlapping window."},
              "evaluation": {"config": {"short_rubert_weight": .55, "long_rubert_weight": .45, "token_boundary": 512, "threshold": .525},
                             "previous_intent_context": old_result, "conflict_resolved_candidate": new_result}}
    out = ROOT / "work/conflict_resolved_candidate_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"phase":"evaluation_done","report":str(out),"previous":old_result["manual_unseen"],
                      "candidate":new_result["manual_unseen"],"ood_previous":old_result["ood"],"ood_candidate":new_result["ood"],
                      "secret_submission":"not generated by the training script"},ensure_ascii=False,indent=2),flush=True)


if __name__ == "__main__": main()
