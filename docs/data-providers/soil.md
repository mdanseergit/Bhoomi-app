# Soil Data Strategy & Normalization

## Data Separation Principle

BHOOMI strictly maintains four distinct soil measurement domains:
1. **Laboratory Soil Tests**: Wet chemistry lab tests (e.g. Soil Health Card, certified testing labs). Measures true nutrient saturation and organic matter.
2. **In-situ Field Sensors**: Capacitive/frequency domain reflectometry (FDR/TDR) soil probes installed on the farm. Measures real-time volumetric water content.
3. **Satellite Soil Moisture**: Microwave radiometer/scatterometer estimations (e.g. Sentinel-1 SAR, SMAP). Measures surface dielectric properties (top 5 cm).
4. **Modelled / Pedotransfer Data**: Soil grids or algorithmic models derived from topographical and climatic covariates.

> **Absolute Rule**: Satellite soil moisture estimates are NEVER represented as equivalent to laboratory soil test data.

## 12 Canonical Nutrients & Physical Ranges
| Nutrient Parameter | Unit | Physical Range | Rejection Threshold |
|---|---|---|---|
| pH | index | 3.0 – 11.0 | < 2.5 or > 12.0 |
| Organic Carbon (OC) | % | 0.05 – 5.0 | > 10.0% |
| Nitrogen (N) | kg/ha | 10 – 600 | < 0 or > 1500 |
| Phosphorus (P) | kg/ha | 1 – 150 | < 0 or > 500 |
| Potassium (K) | kg/ha | 20 – 800 | < 0 or > 2000 |
| Sulphur (S) | ppm | 1 – 100 | < 0 or > 500 |
| Zinc (Zn) | ppm | 0.1 – 20 | < 0 or > 100 |
| Boron (B) | ppm | 0.05 – 10 | < 0 or > 50 |
| Iron (Fe) | ppm | 0.5 – 50 | < 0 or > 200 |
| Manganese (Mn) | ppm | 0.5 – 50 | < 0 or > 200 |
| Copper (Cu) | ppm | 0.05 – 15 | < 0 or > 100 |
| Electrical Conductivity (EC) | dS/m | 0.01 – 16.0 | < 0 or > 30.0 |

## Ingestion & Validation Flow
```
Soil Health Card API / Lab CSV Upload
                  │
                  ▼
         Unit Normalization
                  │
                  ▼
      Physical Range Validation
                  │
                  ▼
         Data Quality Check
                  │
          ┌───────┴───────┐
          ▼               ▼
     Valid Score     Invalid Value
     (Store in DB)   (Flag WARNING/REJECT,
                      do not pass to AI)
```
