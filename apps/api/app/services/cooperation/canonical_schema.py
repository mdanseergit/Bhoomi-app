"""
Canonical agricultural data schema shared across all state adapters
(PRODUCT SPEC section 28). Every `StateDataAdapter` converts its local
format into this schema before it can be shared through the cooperation
network -- raw state-local formats never leak across the boundary.
"""
from typing import Any, TypedDict

SCHEMA_VERSION = "agri.schema.v1"


class CanonicalRecord(TypedDict, total=False):
    schema_version: str
    farm: dict[str, Any]
    soil: dict[str, Any]
    weather: dict[str, Any]
    vegetation: dict[str, Any]
    risk: dict[str, Any]
    source_state: str
