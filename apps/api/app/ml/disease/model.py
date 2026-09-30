"""
BHOOMI Crop Doctor -- development baseline classifier.

IMPORTANT / HONESTY NOTICE
--------------------------
This module ships a deterministic, image-statistics-based heuristic
classifier (color/texture signal analysis), NOT a trained convolutional
neural network. Training and shipping a production-grade EfficientNet /
MobileNet / ConvNeXt / ViT disease classifier requires a licensed,
labeled agricultural image dataset that is not available in this
environment.

The architecture is intentionally built so a real trained model can be
dropped in with zero changes to calling code:

    class DiseaseClassifier(Protocol):
        def predict(self, image: PIL.Image.Image, crop: str) -> ClassificationResult: ...

Production upgrade path: export a trained EfficientNet/MobileNet/ConvNeXt
classifier to ONNX, load it with `onnxruntime.InferenceSession` inside a new
`OnnxDiseaseClassifier`, and register it in
`app/integrations/disease/factory.py` -- no other code needs to change.

Every prediction produced by the current heuristic baseline is labeled
`is_dev_model=True` end-to-end (model registry, API response, UI) and is
always phrased as "possible disease", never a confirmed diagnosis.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

_LABELS_PATH = Path(__file__).parent / "labels.json"
with open(_LABELS_PATH) as f:
    _LABELS = json.load(f)

CLASS_IDS = [c["id"] for c in _LABELS["classes"]]


@dataclass
class ClassificationResult:
    predicted_class: str
    confidence: float
    top_k: list[dict]
    model_version: str
    is_dev_model: bool = True


def _image_signal_features(img: Image.Image) -> dict:
    arr = np.asarray(img.resize((128, 128))).astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    green_dominance = float(np.mean(g - (r + b) / 2))
    brown_yellow_signal = float(np.mean(np.clip((r + g) / 2 - b, 0, 1)))
    dark_spot_ratio = float(np.mean(((r + g + b) / 3) < 0.25))
    texture_variance = float(np.var(arr))
    brightness = float(np.mean(arr))

    return {
        "green_dominance": green_dominance,
        "brown_yellow_signal": brown_yellow_signal,
        "dark_spot_ratio": dark_spot_ratio,
        "texture_variance": texture_variance,
        "brightness": brightness,
    }


def classify(img: Image.Image, crop: str) -> ClassificationResult:
    """Deterministic heuristic classification from color/texture signals.

    This purposefully favors caution: low-signal / ambiguous images bias
    toward lower confidence rather than a confident-sounding wrong answer.
    """
    feats = _image_signal_features(img)
    scores: dict[str, float] = {c: 0.05 for c in CLASS_IDS}

    scores["healthy"] += max(0.0, feats["green_dominance"]) * 1.6
    scores["healthy"] += 0.2 if feats["dark_spot_ratio"] < 0.03 else 0.0

    scores["leaf_spot"] += feats["dark_spot_ratio"] * 3.0
    scores["blight"] += feats["brown_yellow_signal"] * 1.8 + feats["dark_spot_ratio"] * 1.2
    scores["rust"] += feats["brown_yellow_signal"] * 1.3
    scores["powdery_mildew"] += max(0.0, feats["brightness"] - 0.65) * 2.0
    scores["nutrient_deficiency"] += max(0.0, feats["brown_yellow_signal"] - feats["dark_spot_ratio"]) * 1.4
    scores["pest_damage"] += feats["texture_variance"] * 2.5

    total = sum(scores.values()) or 1.0
    normalized = {k: v / total for k, v in scores.items()}
    ranked = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)

    top_class, top_score = ranked[0]
    # Cap displayed confidence conservatively -- this is a heuristic, not a
    # validated model, so we never claim near-certainty.
    confidence = round(min(0.9, max(0.35, top_score * 1.8)), 2)

    top_k = [{"class": cls, "confidence": round(min(0.95, sc * 1.8), 3)} for cls, sc in ranked[:3]]

    return ClassificationResult(
        predicted_class=top_class,
        confidence=confidence,
        top_k=top_k,
        model_version=_LABELS["version"],
        is_dev_model=True,
    )
