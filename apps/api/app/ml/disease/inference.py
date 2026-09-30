from PIL import Image

from app.ml.disease.model import ClassificationResult, classify
from app.ml.disease.preprocess import resize_for_model


def run_inference(image: Image.Image, crop: str) -> ClassificationResult:
    prepared = resize_for_model(image)
    return classify(prepared, crop)


def severity_from_confidence(confidence: float, predicted_class: str) -> str:
    if predicted_class == "healthy":
        return "none"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "moderate"
    return "low"
