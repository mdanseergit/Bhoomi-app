"""
Crop Doctor pipeline (PRODUCT SPEC section 25):

    image -> validation -> resize/preprocessing -> disease model
          -> prediction -> confidence -> severity -> LLM explanation -> advisory
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError, ValidationFailedError
from app.core.prompts import SYSTEM_PROMPT
from app.integrations.disease.base import DiseaseModelProvider
from app.integrations.disease.heuristic_provider import HeuristicDiseaseModelProvider
from app.integrations.storage.local_storage import LocalStorageBackend
from app.ml.disease.preprocess import ImageValidationError, validate_and_load
from app.models.advisory import Advisory, AdvisoryType, ReviewStatus, Severity
from app.models.disease import DiseaseScan
from app.models.farm import Farm
from app.services.ai_service import AIService

_SEVERITY_TO_ADVISORY = {
    "high": Severity.HIGH,
    "moderate": Severity.MODERATE,
    "low": Severity.LOW,
    "none": Severity.LOW,
}

def _limitations(provider: DiseaseModelProvider) -> list[str]:
    """Caveats that describe the model actually used for this scan.

    A validated model still needs the field-advice and image-quality caveats,
    but it must not be described as a development-stage classifier.
    """
    if provider.is_validated:
        return [
            "This is an automated prediction, not a certified diagnosis.",
            "Lighting, image quality, and camera angle can materially change the result.",
            "For high-value crops or uncertain cases, please consult a qualified agricultural officer or agronomist before taking action.",
        ]
    return [
        "This result is produced by BHOOMI's development-stage image classifier and is not a certified diagnosis.",
        "Lighting, image quality, and camera angle can materially change the result.",
        "For high-value crops or uncertain cases, please consult a qualified agricultural officer or agronomist before taking action.",
    ]


# Provider name -> implementation. Registering a real, validated backend here
# is what makes DISEASE_MODEL_PROVIDER selectable; an unregistered name falls
# back to the heuristic and is refused in production.
_PROVIDERS: dict[str, type[DiseaseModelProvider]] = {
    "heuristic": HeuristicDiseaseModelProvider,
    "heuristic-baseline": HeuristicDiseaseModelProvider,
    "bhoomi-vision": HeuristicDiseaseModelProvider,
    "bhoomi-vision-v1": HeuristicDiseaseModelProvider,
}


class DiseaseService:
    def __init__(self) -> None:
        self.model_provider = self._resolve_provider()
        self.storage = LocalStorageBackend()
        self.ai_service = AIService()

    @staticmethod
    def _resolve_provider() -> DiseaseModelProvider | None:
        """Build the backend named by DISEASE_MODEL_PROVIDER.

        Only providers registered in `_PROVIDERS` can be selected. An unknown
        name falls back to the heuristic rather than failing open, and the
        production gate then refuses it. `none` means the feature is switched
        off, which is reported per request rather than at import time so the
        rest of the API keeps working.
        """
        configured = (settings.DISEASE_MODEL_PROVIDER or "").strip().lower()
        if configured in ("", "none"):
            return None
        provider_cls = _PROVIDERS.get(configured, HeuristicDiseaseModelProvider)
        return provider_cls()

    def _assert_model_available(self) -> None:
        """Refuse to present an unvalidated classifier as a diagnosis.

        The decision is made from the resolved provider's own ``is_validated``
        flag, not from the configuration string, so a deployment cannot bypass
        this check by naming a provider that does not exist.
        """
        if self.model_provider is None:
            raise ProviderUnavailableError(
                "Crop Doctor image diagnosis is not enabled on this deployment. "
                "No disease-detection model is configured, so no diagnosis can be "
                "produced. Please consult a qualified agricultural officer.",
                log_context={"feature": "crop_doctor", "configured_provider": None},
            )
        if settings.is_production and not self.model_provider.is_validated:
            raise ProviderUnavailableError(
                "Crop Doctor image diagnosis is not enabled on this deployment. "
                f"The configured model '{self.model_provider.name}' is not a validated "
                "diagnostic model, so no diagnosis can be produced. Please consult a "
                "qualified agricultural officer.",
                log_context={
                    "feature": "crop_doctor",
                    "configured_provider": settings.DISEASE_MODEL_PROVIDER or None,
                    "resolved_provider": self.model_provider.name,
                    "is_validated_model": self.model_provider.is_validated,
                },
            )

    def analyze(
        self,
        db: Session,
        *,
        farm: Farm,
        user_id: str,
        image_bytes: bytes,
        content_type: str,
        crop: str | None,
        with_ai: bool = True,
    ) -> dict:
        self._assert_model_available()

        try:
            image = validate_and_load(image_bytes, content_type, settings.MAX_UPLOAD_SIZE_MB)
        except ImageValidationError as exc:
            raise ValidationFailedError(str(exc)) from exc

        crop_name = crop or farm.current_crop or "general"
        prediction = self.model_provider.predict(image, crop_name)

        ext = "jpg" if content_type == "image/jpeg" else ("png" if content_type == "image/png" else "webp")
        stored_key = self.storage.save(image_bytes, ext, folder="disease_scans")

        recommended_actions = self._deterministic_actions(prediction.predicted_class, prediction.severity)
        limitations = _limitations(self.model_provider)

        scan = DiseaseScan(
            farm_id=farm.id,
            user_id=user_id,
            image_path=stored_key,
            crop=crop_name,
            possible_disease=prediction.predicted_class,
            confidence=prediction.confidence,
            severity=prediction.severity,
            top_k=prediction.top_k,
            recommended_actions=recommended_actions,
            limitations=limitations,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        ai_explanation = None
        ai_provider = None
        if with_ai:
            evidence = {
                "crop": crop_name,
                "possible_disease": prediction.predicted_class,
                "confidence": prediction.confidence,
                "severity": prediction.severity,
                "is_dev_model": prediction.is_dev_model,
                "top_k": prediction.top_k,
            }
            prompt = (
                f"Structured Crop Doctor result (JSON): {evidence}\n\n"
                "Explain this result to a farmer in 2-4 simple sentences. Use the phrase "
                "'possible disease' rather than a confirmed diagnosis. If confidence is below "
                "0.6, explicitly recommend expert verification."
            )
            ai_explanation, ai_provider = self.ai_service.explain(
                db, user_id=user_id, request_type="disease_explanation", user_prompt=prompt, system_prompt=SYSTEM_PROMPT
            )
            scan.llm_explanation = ai_explanation
            db.commit()

        advisory = Advisory(
            farm_id=farm.id,
            type=AdvisoryType.DISEASE,
            severity=_SEVERITY_TO_ADVISORY.get(prediction.severity, Severity.LOW),
            title=f"Possible {prediction.predicted_class.replace('_', ' ')} detected",
            summary=ai_explanation or f"BHOOMI's Crop Doctor flagged a possible {prediction.predicted_class.replace('_', ' ')} with {prediction.confidence:.0%} confidence.",
            actions=[{"title": a, "priority": "medium", "reason": "Recommended follow-up after crop image analysis."} for a in recommended_actions],
            evidence=[{"source": "disease_scan", "value": f"{prediction.predicted_class} ({prediction.confidence:.0%})", "timestamp": scan.created_at.isoformat()}],
            source_references=[{
                "source": "crop_doctor_model",
                "authority": (
                    f"BHOOMI validated disease model ({self.model_provider.name})"
                    if self.model_provider.is_validated
                    else f"BHOOMI development classifier ({self.model_provider.name}, not clinically validated)"
                ),
            }],
            confidence=prediction.confidence,
            generated_by="ai" if with_ai else "rule_engine",
            review_status=ReviewStatus.PENDING if prediction.severity in ("high", "moderate") else ReviewStatus.AUTO_APPROVED,
        )
        db.add(advisory)
        db.commit()

        return {
            "scan_id": str(scan.id),
            "crop": crop_name,
            "possible_disease": prediction.predicted_class,
            "confidence": prediction.confidence,
            "severity": prediction.severity,
            "top_k": prediction.top_k,
            "recommended_actions": recommended_actions,
            "limitations": limitations,
            "is_dev_model": prediction.is_dev_model,
            "ai_explanation": ai_explanation,
            "ai_provider_used": ai_provider,
        }

    @staticmethod
    def _deterministic_actions(predicted_class: str, severity: str) -> list[str]:
        if predicted_class == "healthy":
            return ["Continue routine monitoring.", "Recheck in 5-7 days or after any visible change."]
        base = [
            "Isolate/monitor the affected plants and surrounding rows.",
            "Take 2-3 more photos from different leaves to confirm the pattern.",
        ]
        if severity in ("high", "moderate"):
            base.append("Consult a qualified agricultural officer or agronomist before applying any treatment.")
        return base
