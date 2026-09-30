from pydantic import BaseModel, Field


class AdvisoryAction(BaseModel):
    title: str
    priority: str = Field(pattern="^(low|medium|high)$")
    reason: str


class EvidenceItem(BaseModel):
    source: str
    value: str
    timestamp: str


class AdvisoryOut(BaseModel):
    id: str
    farm_id: str
    type: str
    severity: str
    title: str
    summary: str
    actions: list[dict]
    evidence: list[dict]
    source_references: list[dict]
    confidence: float
    generated_by: str
    review_status: str
    created_at: str


class StructuredAIAdvisory(BaseModel):
    """Schema every LLM-generated advisory JSON payload must validate
    against before being stored or shown (see PRODUCT SPEC section 51).
    If validation fails, the caller retries once, then falls back to the
    deterministic advisory text."""

    summary: str
    risk_level: str = Field(pattern="^(low|moderate|high|critical)$")
    confidence: float = Field(ge=0, le=1)
    actions: list[AdvisoryAction] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
