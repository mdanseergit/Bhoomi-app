"""
StateDataAdapter implementations.

Each state's local field names, units, and terminology are mapped onto the
canonical `agri.schema.v1` structure (PRODUCT SPEC sections 28-29). These
are development/demo adapters illustrating the mapping pattern for three
states; they do not represent an existing government integration.
"""
from abc import ABC, abstractmethod
from typing import Any

from app.services.cooperation.canonical_schema import SCHEMA_VERSION, CanonicalRecord


class StateDataAdapter(ABC):
    state_name: str

    @abstractmethod
    def to_canonical(self, local_record: dict[str, Any]) -> CanonicalRecord:
        ...


class TamilNaduAdapter(StateDataAdapter):
    state_name = "Tamil Nadu"

    # local field -> canonical path mapping (documented explicitly, not implicit "magic")
    FIELD_MAP = {
        "soil_N": "soil.nitrogen",
        "soil_P": "soil.phosphorus",
        "soil_K": "soil.potassium",
        "mandal": "farm.location.taluk",
        "crop_name_ta": "farm.crop.name",
    }

    def to_canonical(self, local_record: dict[str, Any]) -> CanonicalRecord:
        return {
            "schema_version": SCHEMA_VERSION,
            "farm": {
                "location": {
                    "state": "Tamil Nadu",
                    "district": local_record.get("district"),
                    "taluk": local_record.get("mandal"),
                },
                "crop": {"name": local_record.get("crop_name_ta") or local_record.get("crop")},
                "season": {"name": local_record.get("season")},
            },
            "soil": {
                "nitrogen": local_record.get("soil_N"),
                "phosphorus": local_record.get("soil_P"),
                "potassium": local_record.get("soil_K"),
            },
            "weather": {},
            "vegetation": {},
            "risk": {},
            "source_state": "Tamil Nadu",
        }


class KarnatakaAdapter(StateDataAdapter):
    state_name = "Karnataka"

    FIELD_MAP = {
        "n_kg_ha": "soil.nitrogen",
        "p_kg_ha": "soil.phosphorus",
        "k_kg_ha": "soil.potassium",
        "taluka": "farm.location.taluk",
    }

    def to_canonical(self, local_record: dict[str, Any]) -> CanonicalRecord:
        return {
            "schema_version": SCHEMA_VERSION,
            "farm": {
                "location": {
                    "state": "Karnataka",
                    "district": local_record.get("district"),
                    "taluk": local_record.get("taluka"),
                },
                "crop": {"name": local_record.get("crop")},
                "season": {"name": local_record.get("season")},
            },
            "soil": {
                "nitrogen": local_record.get("n_kg_ha"),
                "phosphorus": local_record.get("p_kg_ha"),
                "potassium": local_record.get("k_kg_ha"),
            },
            "weather": {},
            "vegetation": {},
            "risk": {},
            "source_state": "Karnataka",
        }


class KeralaAdapter(StateDataAdapter):
    state_name = "Kerala"

    FIELD_MAP = {
        "soil_nitrogen_pct": "soil.nitrogen",
        "panchayat": "farm.location.village",
    }

    def to_canonical(self, local_record: dict[str, Any]) -> CanonicalRecord:
        return {
            "schema_version": SCHEMA_VERSION,
            "farm": {
                "location": {
                    "state": "Kerala",
                    "district": local_record.get("district"),
                    "village": local_record.get("panchayat"),
                },
                "crop": {"name": local_record.get("crop")},
                "season": {"name": local_record.get("season")},
            },
            "soil": {"nitrogen": local_record.get("soil_nitrogen_pct")},
            "weather": {},
            "vegetation": {},
            "risk": {},
            "source_state": "Kerala",
        }


ADAPTERS: dict[str, StateDataAdapter] = {
    "Tamil Nadu": TamilNaduAdapter(),
    "Karnataka": KarnatakaAdapter(),
    "Kerala": KeralaAdapter(),
}


def get_adapter(state: str) -> StateDataAdapter | None:
    return ADAPTERS.get(state)
