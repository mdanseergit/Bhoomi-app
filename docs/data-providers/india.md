# Indian Agricultural Data Providers

## 1. India Meteorological Department (IMD)

### Purpose
Official operational national weather provider for India, providing observations, short/medium-range forecasts, agrometeorological advisories, and weather warning bulletins across districts and taluks.

### API Architecture
- **Base URL**: Set via `IMD_API_BASE_URL` (e.g. `https://api.imd.gov.in/v1` or configured national portal endpoint)
- **Protocol**: REST over HTTPS, JSON payloads
- **Endpoints**:
  - `/observations/current`: Station-level temperature, humidity, rainfall, wind speed, pressure
  - `/forecasts/district`: 5-day block/district forecast & agromet advisories

### Authentication & Secrets
- **Type**: API Key (Header `X-API-KEY` or Bearer token)
- **Environment Variables**:
  ```bash
  IMD_API_BASE_URL=https://api.imd.gov.in/v1
  IMD_API_KEY=your_imd_api_key_here
  ```
- **Failsafe**: Never hardcode credentials. If credentials are not present, BHOOMI marks the provider as `CONFIGURED BUT AUTHENTICATION REQUIRED` without inventing simulated weather.

### Ingested Data Fields & Normalization
| Upstream Field | Canonical BHOOMI Field | Canonical Unit | Conversion |
|---|---|---|---|
| `TEMP` / `temperature` | `weather.temperature_c` | °C | Normalized from Celsius |
| `RH` / `humidity` | `weather.humidity_pct` | % | Clamped 0–100% |
| `RAIN_MM` / `rainfall` | `weather.rainfall_mm` | mm | Verified non-negative |
| `POP` / `rain_prob` | `weather.rain_probability_pct` | % | Clamped 0–100% |
| `WSPD_KMPH` | `weather.wind_speed_mps` | m/s | `km/h * 0.277778` |

### Natural Update Frequency & Freshness
- **Observation Frequency**: 15–60 minutes
- **Freshness Classification**:
  - `LIVE`: < 1 hour old
  - `RECENT`: 1–3 hours old
  - `STALE`: 3–24 hours old
  - `OUTDATED`: > 24 hours old

### Rate Limits & Failure Handling
- **Rate Limit**: Default 120 requests/minute
- **Backoff Policy**: Exponential backoff (1s, 2s, 4s), max 3 attempts
- **Automatic Failover**: IMD failure triggers automatic failover to the global agroclimatology provider (`NASA POWER`), explicitly tagging source provenance as `NASA POWER (Fallback)` in all records.

---

## 2. Soil Health Card (SHC) System

### Purpose
Official laboratory soil testing framework of the Ministry of Agriculture & Farmers Welfare (Government of India).

### API Architecture
- **Base URL**: Set via `SOIL_HEALTH_CARD_BASE_URL`
- **Protocol**: REST / SOAP integration gateway
- **Endpoints**:
  - `/soil-test/sample`: By sample registration number or GPS coordinates

### Authentication
- **Type**: Authorized client credentials or authorized departmental API key
- **Environment Variables**:
  ```bash
  SOIL_HEALTH_CARD_BASE_URL=https://soilhealth.dac.gov.in/api
  SOIL_HEALTH_CARD_API_KEY=your_shc_api_key_here
  ```

### Ingested Data Fields & 12 Soil Nutrients
Canonical schema maps the full 12 parameters:
1. `pH` (acidity / alkalinity)
2. `Electrical Conductivity (EC)` (dS/m)
3. `Organic Carbon (OC)` (%)
4. `Nitrogen (N)` (kg/ha)
5. `Phosphorus (P)` (kg/ha)
6. `Potassium (K)` (kg/ha)
7. `Sulphur (S)` (ppm / mg/kg)
8. `Zinc (Zn)` (ppm)
9. `Boron (B)` (ppm)
10. `Iron (Fe)` (ppm)
11. `Manganese (Mn)` (ppm)
12. `Copper (Cu)` (ppm)

### Measurement Integrity
- **Lab vs Satellite**: Lab test observations are strictly distinguished from satellite soil moisture estimates. Satellite data is never substituted for missing laboratory chemical nutrient tests.

---

## 3. ISRO / Bhoonidhi (NRSC)

### Purpose
National Remote Sensing Centre (NRSC) / ISRO Earth observation portal for Indian thematic EO products, including NDVI, Sentinel-2/1 datasets, and regional vegetation indices.

### API Architecture
- **Base URL**: Set via `BHOONIDHI_API_BASE_URL` (supports STAC and product query APIs)
- **Environment Variables**:
  ```bash
  BHOONIDHI_API_BASE_URL=https://bhoonidhi.nrsc.gov.in/api
  BHOONIDHI_API_KEY=your_bhoonidhi_api_key_here
  ```

### Products Supported
- Sentinel-2 MSI Level-2A / Level-1C
- Resourcesat-2 / 2A AWiFS / LISS-III
- ISRO Open EO thematic vegetation condition products

### Fallback Policy
When Bhoonidhi credentials are not provided, system flags status as `CONFIGURED BUT AUTHENTICATION REQUIRED` and routes spatial queries to Copernicus Data Space Ecosystem (CDSE) global fallback.
