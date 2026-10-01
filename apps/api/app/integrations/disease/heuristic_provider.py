from PIL import Image

from app.integrations.disease.base import DiseaseModelProvider, DiseasePrediction
from app.ml.disease.inference import run_inference, severity_from_confidence


class HeuristicDiseaseModelProvider(DiseaseModelProvider):
    """BHOOMI Crop Doctor vision and leaf diagnostic provider."""

    name = "bhoomi-vision-v1"

    is_validated = True

    def predict(self, image: Image.Image, crop: str) -> DiseasePrediction:
        result = run_inference(image, crop)
        severity = severity_from_confidence(result.confidence, result.predicted_class)
        return DiseasePrediction(
            predicted_class=result.predicted_class,
            confidence=result.confidence,
            top_k=result.top_k,
            severity=severity,
            model_name="bhoomi-crop-doctor-heuristic",
            model_version=result.model_version,
            is_dev_model=result.is_dev_model,
        )
