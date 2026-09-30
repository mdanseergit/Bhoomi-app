"""
Canonical Unit Normalizer for BHOOMI Data Network.
Transforms all external measurements into standard SI/agricultural units,
recording the original value, original unit, and conversion method.
"""
from typing import Optional
from app.integrations.data_network.base import UnitConversionRecord


class UnitNormalizer:
    @staticmethod
    def normalize_temperature(val: Optional[float], unit: str = "C") -> tuple[Optional[float], Optional[UnitConversionRecord]]:
        if val is None:
            return None, None
        unit_clean = unit.strip().upper()
        if unit_clean in ("C", "CELSIUS"):
            return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "°C", "identity")
        elif unit_clean in ("F", "FAHRENHEIT"):
            c = (val - 32) * 5.0 / 9.0
            return round(c, 2), UnitConversionRecord(val, unit, round(c, 2), "°C", "(F - 32) * 5/9")
        elif unit_clean in ("K", "KELVIN"):
            c = val - 273.15
            return round(c, 2), UnitConversionRecord(val, unit, round(c, 2), "°C", "K - 273.15")
        return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "°C", "assumed_celsius")

    @staticmethod
    def normalize_wind_speed(val: Optional[float], unit: str = "km/h") -> tuple[Optional[float], Optional[float], Optional[UnitConversionRecord]]:
        """Returns (speed_ms, speed_kmh, conversion_record)"""
        if val is None:
            return None, None, None
        unit_clean = unit.strip().lower()
        if unit_clean in ("m/s", "mps", "ms"):
            kmh = val * 3.6
            return round(val, 2), round(kmh, 2), UnitConversionRecord(val, unit, round(val, 2), "m/s", "identity")
        elif unit_clean in ("km/h", "kmh", "kph"):
            ms = val / 3.6
            return round(ms, 2), round(val, 2), UnitConversionRecord(val, unit, round(ms, 2), "m/s", "km/h / 3.6")
        elif unit_clean in ("mph", "miles/hour"):
            ms = val * 0.44704
            kmh = val * 1.60934
            return round(ms, 2), round(kmh, 2), UnitConversionRecord(val, unit, round(ms, 2), "m/s", "mph * 0.44704")
        return round(val / 3.6, 2), round(val, 2), UnitConversionRecord(val, unit, round(val / 3.6, 2), "m/s", "assumed_kmh")

    @staticmethod
    def normalize_rainfall(val: Optional[float], unit: str = "mm") -> tuple[Optional[float], Optional[UnitConversionRecord]]:
        if val is None:
            return None, None
        unit_clean = unit.strip().lower()
        if unit_clean in ("mm", "millimetres", "millimeters"):
            return round(max(0.0, val), 2), UnitConversionRecord(val, unit, round(max(0.0, val), 2), "mm", "identity")
        elif unit_clean in ("in", "inch", "inches"):
            mm = val * 25.4
            return round(max(0.0, mm), 2), UnitConversionRecord(val, unit, round(max(0.0, mm), 2), "mm", "inches * 25.4")
        elif unit_clean in ("cm", "centimetres"):
            mm = val * 10.0
            return round(max(0.0, mm), 2), UnitConversionRecord(val, unit, round(max(0.0, mm), 2), "mm", "cm * 10")
        return round(max(0.0, val), 2), UnitConversionRecord(val, unit, round(max(0.0, val), 2), "mm", "assumed_mm")

    @staticmethod
    def normalize_area(val: Optional[float], unit: str = "ha") -> tuple[Optional[float], Optional[UnitConversionRecord]]:
        if val is None:
            return None, None
        unit_clean = unit.strip().lower()
        if unit_clean in ("ha", "hectare", "hectares"):
            return round(val, 4), UnitConversionRecord(val, unit, round(val, 4), "ha", "identity")
        elif unit_clean in ("acre", "acres"):
            ha = val * 0.404686
            return round(ha, 4), UnitConversionRecord(val, unit, round(ha, 4), "ha", "acres * 0.404686")
        elif unit_clean in ("sq_m", "sqm", "m2"):
            ha = val / 10000.0
            return round(ha, 4), UnitConversionRecord(val, unit, round(ha, 4), "ha", "m2 / 10000")
        elif unit_clean in ("bigha",):
            # Standard metric bigha ~ 0.25 ha
            ha = val * 0.25
            return round(ha, 4), UnitConversionRecord(val, unit, round(ha, 4), "ha", "standard bigha * 0.25")
        return round(val, 4), UnitConversionRecord(val, unit, round(val, 4), "ha", "assumed_ha")

    @staticmethod
    def normalize_soil_nutrient(val: Optional[float], parameter: str, unit: str = "kg/ha") -> tuple[Optional[float], Optional[UnitConversionRecord]]:
        """Normalize macro nutrients to kg/ha and micro nutrients to ppm/mg/kg."""
        if val is None:
            return None, None
        unit_clean = unit.strip().lower()
        param = parameter.strip().lower()

        if param in ("nitrogen", "phosphorus", "potassium"):
            # Canonical unit: kg/ha
            if unit_clean in ("kg/ha", "kg_per_ha", "kgha"):
                return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "kg/ha", "identity")
            elif unit_clean in ("ppm", "mg/kg"):
                # Approximate furrow slice (0-15cm, bulk density 1.33 g/cm3) ~ 2.24 kg/ha per ppm
                kg_ha = val * 2.24
                return round(kg_ha, 2), UnitConversionRecord(val, unit, round(kg_ha, 2), "kg/ha", "ppm * 2.24 furrow-slice")
            return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "kg/ha", "assumed_kg_ha")

        elif param in ("sulfur", "zinc", "boron", "iron", "manganese", "copper"):
            # Canonical unit: ppm (mg/kg)
            if unit_clean in ("ppm", "mg/kg", "mg_per_kg"):
                return round(val, 3), UnitConversionRecord(val, unit, round(val, 3), "ppm", "identity")
            elif unit_clean in ("kg/ha",):
                ppm = val / 2.24
                return round(ppm, 3), UnitConversionRecord(val, unit, round(ppm, 3), "ppm", "kg/ha / 2.24")
            return round(val, 3), UnitConversionRecord(val, unit, round(val, 3), "ppm", "assumed_ppm")

        elif param == "organic_carbon":
            # Canonical unit: %
            if unit_clean in ("%", "pct", "percent"):
                return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "%", "identity")
            elif unit_clean in ("g/kg",):
                pct = val / 10.0
                return round(pct, 2), UnitConversionRecord(val, unit, round(pct, 2), "%", "g/kg / 10")
            return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), "%", "assumed_pct")

        elif param == "electrical_conductivity":
            # Canonical unit: dS/m
            if unit_clean in ("ds/m", "ms/cm"):
                return round(val, 3), UnitConversionRecord(val, unit, round(val, 3), "dS/m", "identity")
            elif unit_clean in ("us/cm", "microsiemens/cm"):
                dsm = val / 1000.0
                return round(dsm, 3), UnitConversionRecord(val, unit, round(dsm, 3), "dS/m", "uS/cm / 1000")
            return round(val, 3), UnitConversionRecord(val, unit, round(val, 3), "dS/m", "assumed_ds_m")

        return round(val, 2), UnitConversionRecord(val, unit, round(val, 2), unit, "identity")

    @staticmethod
    def normalize_coordinates(lat: float, lon: float) -> tuple[float, float]:
        """Validate and round WGS84 coordinates."""
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude {lat} out of valid WGS84 range [-90, 90]")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude {lon} out of valid WGS84 range [-180, 180]")
        return round(lat, 6), round(lon, 6)
