"""Optional local RuBERT inference adapter; imported only when explicitly enabled."""
from __future__ import annotations

import numpy as np


class RuBertClassifier:
    def __init__(self, model_dir: str, max_length: int = 512, batch_size: int = 8, window_stride: int = 128):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
        self.model.to(self.device).eval()
        self.max_length = max_length
        self.batch_size = batch_size
        self.window_stride = window_stride

    def predict_proba(self, texts):
        if not texts:
            return np.empty((0, self.model.config.num_labels), dtype=np.float32)
        encoded = self.tokenizer(
            texts, truncation=True, max_length=self.max_length,
            stride=self.window_stride, return_overflowing_tokens=True, padding=False,
        )
        owners = encoded.pop("overflow_to_sample_mapping")
        scores = np.zeros((len(texts), self.model.config.num_labels), dtype=np.float32)
        for start in range(0, len(owners), self.batch_size):
            batch = self.tokenizer.pad(
                {key: value[start:start + self.batch_size] for key, value in encoded.items()},
                padding=True, return_tensors="pt",
            )
            batch = {key: value.to(self.device) for key, value in batch.items()}
            with self.torch.inference_mode():
                logits = self.model(**batch).logits.float()
                window_scores = self.torch.sigmoid(logits).cpu().numpy()
            np.maximum.at(scores, owners[start:start + self.batch_size], window_scores)
        return scores


class ProbabilityBlend:
    def __init__(self, models, weights):
        if len(models) != len(weights) or not models:
            raise ValueError("models and weights must have the same nonzero length")
        if not np.isclose(sum(weights), 1.0):
            raise ValueError("weights must sum to one")
        self.models = tuple(models)
        self.weights = tuple(weights)

    def predict_proba(self, texts):
        return sum(weight * model.predict_proba(texts)
                   for model, weight in zip(self.models, self.weights))


class AdaptiveProbabilityBlend:
    """Use a slightly larger RuBERT share for short ads and scan long ads fully."""
    def __init__(self, cpu_model, rubert_model, short_rubert_weight=0.55,
                 long_rubert_weight=0.45, token_limit=512):
        if not 0 <= short_rubert_weight <= 1 or not 0 <= long_rubert_weight <= 1:
            raise ValueError("ensemble weights must be between 0 and 1")
        if token_limit < 1:
            raise ValueError("token_limit must be positive")
        self.cpu_model = cpu_model
        self.rubert_model = rubert_model
        self.short_rubert_weight = float(short_rubert_weight)
        self.long_rubert_weight = float(long_rubert_weight)
        self.token_limit = int(token_limit)

    def predict_proba(self, texts):
        if not texts:
            return np.empty((0, 5), dtype=np.float32)
        cpu_scores = self.cpu_model.predict_proba(texts)
        rubert_scores = self.rubert_model.predict_proba(texts)
        tokenized = self.rubert_model.tokenizer(
            texts, add_special_tokens=True, truncation=False, padding=False,
        )
        weights = np.asarray([
            self.short_rubert_weight if len(ids) <= self.token_limit else self.long_rubert_weight
            for ids in tokenized["input_ids"]
        ], dtype=np.float32)[:, None]
        return cpu_scores * (1.0 - weights) + rubert_scores * weights
