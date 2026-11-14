import numpy as np
import pytest

from app.transformer_classifier import ProbabilityBlend
from app.main import choose_local_classifier_backend


class ConstantClassifier:
    def __init__(self, value):
        self.value = value

    def predict_proba(self, texts):
        return np.full((len(texts), 2), self.value)


def test_probability_blend_averages_classifier_scores():
    blend = ProbabilityBlend((ConstantClassifier(.2), ConstantClassifier(.8)), (.5, .5))
    np.testing.assert_allclose(blend.predict_proba(["one", "two"]), [[.5, .5], [.5, .5]])


def test_probability_blend_requires_normalized_weights():
    with pytest.raises(ValueError, match="sum to one"):
        ProbabilityBlend((ConstantClassifier(.2), ConstantClassifier(.8)), (.25, .25))


def test_auto_backend_uses_transformer_only_when_weights_exist(tmp_path):
    weights = tmp_path / "rubert"
    assert choose_local_classifier_backend("auto", weights) == "cpu"
    weights.mkdir()
    assert choose_local_classifier_backend("auto", weights) == "ensemble"
    assert choose_local_classifier_backend("cpu", weights) == "cpu"
