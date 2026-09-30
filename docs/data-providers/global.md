# Global Agricultural Data Providers

## 1. Copernicus Data Space Ecosystem (CDSE)

### Purpose
European Space Agency (ESA) Earth Observation programme providing open Sentinel-1 (SAR) and Sentinel-2 (Multispectral Optical) satellite observations for vegetation monitoring and agricultural land intelligence.

### API Architecture
- **STAC Catalogue API**: `https://catalogue.dataspace.copernicus.eu/stac`
- **Product & OData API**: `https://zipper.dataspace.copernicus.eu/odata/v1`
- **openEO / Processing API**: Sentinel Hub compatible endpoints

### Authentication
- Open STAC catalogue searches are publicly queryable.
- High-resolution band downloads and processing require OAuth2 credentials:
  ```bash
  COPERNICUS_CLIENT_ID=your_client_id
  COPERNICUS_CLIENT_SECRET=your_client_secret
  ```

### Data Fields & Spectral Indices
- `B04` (Red, 665 nm) and `B08` (NIR, 842 nm)
- Computed Indices:
  - **NDVI** = `(NIR - Red) / (NIR + Red)`
  - **EVI** = `2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))`
  - **NDRE** = `(NIR - RedEdge) / (NIR + RedEdge)`
  - **NDWI** = `(NIR - SWIR) / (NIR + SWIR)`
- **Cloud Masking**: Scenes with `eo:cloud_cover > 30%` are automatically filtered out.

### Revisit Schedule & Freshness
- Revisit cycle: 5 days at equator (2–3 days at mid-latitudes).
- Observations are tagged `RECENT` when < 5 days old, and `STALE` when older than 10 days.

---

## 2. NASA POWER Agroclimatology

### Purpose
NASA Prediction of Worldwide Energy Resources (POWER) Project provides free, globally available solar and meteorological data designed for agricultural modeling and renewable energy applications.

### API Architecture
- **Base URL**: `https://power.larc.nasa.gov/api`
- **Endpoint**: `/temporal/daily/point` and `/temporal/hourly/point`
- **Authentication**: None required (Public Scientific Open Access)
- **Role in BHOOMI**: Global Climate & Weather Fallback. Used when national weather services (e.g. IMD) are unreachable or in countries without a dedicated national meteorological API.

### Ingested Parameters
- `T2M`: Temperature at 2 meters (°C)
- `RH2M`: Relative Humidity at 2 meters (%)
- `PRECTOTCORR`: Precipitation corrected (mm/day)
- `WS2M`: Wind speed at 2 meters (m/s)
- `ALLSKY_SFC_SW_DWN`: All-sky solar insolation (MJ/m²/day)

---

## 3. FAOSTAT (Food and Agriculture Organization)

### Purpose
UN Food and Agriculture Organization statistical platform covering agricultural production, harvested area, yield history, and trade across 245 countries and territories.

### API Architecture
- **Base URL**: `https://fenixservices.fao.org/faostat/api/v1`
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 3.0 IGO (CC BY-NC-SA 3.0 IGO)

### Agricultural Scope
- Regional and national historical baselines
- Crop yield benchmarking (e.g., district yield vs national average)
- Country-level comparison indicators
- **Integrity Rule**: FAOSTAT statistics provide macroeconomic and historical context; they are NEVER used to fabricate individual farm-level sensor measurements.
