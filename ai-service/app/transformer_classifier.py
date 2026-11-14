"""Optional local RuBERT inference adapter; imported only when explicitly enabled."""
from __future__ import annotations

import numpy as np


class RuBertClassifier:
    def __init__(self, model_dir: str, max_length: int = 512, batch_size: int = 8):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
        self.model.to(self.device).eval()
        self.max_length = max_length
        self.batch_size = batch_size

    def predict_proba(self, texts):
        scores = []
        for start in range(0, len(texts), self.batch_size):
            encoded = self.tokenizer(
                texts[start:start + self.batch_size], truncation=True,
                max_length=self.max_length, padding=True, return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with self.torch.inference_mode():
                logits = self.model(**encoded).logits.float()
                scores.extend(self.torch.sigmoid(logits).cpu().numpy())
        return np.asarray(scores)


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
