from abc import ABC, abstractmethod
from dataclasses import dataclass

from PIL import Image


@dataclass
class DiseasePrediction:
    predicted_class: str
    confidence: float
    top_k: list[dict]
    severity: str
    model_name: str
    model_version: str
    is_dev_model: bool


class DiseaseModelProvider(ABC):
    """A disease-detection backend.

    ``is_validated`` must only be True for a model that has been validated
    against labelled field data for the crops it claims to diagnose. The
    production gate in :class:`~app.services.disease_service.DiseaseService`
    reads this flag rather than a configuration string, so a deployment cannot
    make an unvalidated model look validated simply by naming a provider.
    """

    #: Human-readable identifier for the backend.
    name: str = "unnamed"

    #: True only for a clinically/agronomically validated model.
    is_validated: bool = False

    @abstractmethod
    def predict(self, image: Image.Image, crop: str) -> DiseasePrediction:
        ...
