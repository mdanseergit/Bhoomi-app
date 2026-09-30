# Satellite & Earth Observation Data Architecture

## Earth Observation Pipeline

BHOOMI utilizes multispectral satellite imagery from ISRO Bhoonidhi and Copernicus Data Space Ecosystem (Sentinel-2 / Sentinel-1).

### Spatial & Temporal Ingestion Workflow
```
             Farm Polygon / Coordinates
                         │
                         ▼
             Bounding Box Calculation
                         │
                         ▼
        STAC Query with Date Range & Cloud Filter
              (eo:cloud_cover <= 30%)
                         │
                         ▼
             Spectral Bands Retrieval
                   (B04, B08, B02)
                         │
                         ▼
             Band Math & Index Calculation
               NDVI = (NIR - Red) / (NIR + Red)
               EVI  = 2.5 * ((NIR - Red) / ...)
                         │
                         ▼
             Spatial Zonal Aggregation
                 over Farm Boundary
                         │
                         ▼
             Persisted Observation &
               Historical Trend Delta
```

## Anti-Fabrication Principles
1. **Spectral Band Requirement**: If required spectral bands are unavailable or obscured by heavy cloud cover, BHOOMI does NOT invent an NDVI value.
2. **Revisit Rate**: Satellites operate on physical orbital revisit cycles (typically 5 days). The UI reflects this explicitly (`Captured X days ago`) rather than claiming "real-time satellite telemetry".
3. **No Excessive Ingestion**: Queries are strictly bounded to the specific farm bounding box and relevant time window. Full satellite tile scenes are not downloaded unnecessarily.

## Canonical Schema
- `ndvi`: Mean Normalized Difference Vegetation Index (-1.0 to +1.0)
- `evi`: Enhanced Vegetation Index (-1.0 to +1.0)
- `trend_7d_pct`: Percentage change relative to the preceding cloud-free acquisition
- `cloud_coverage_pct`: Scene cloud cover percentage
- `processing_level`: e.g. `Level-2A (Bottom-of-Atmosphere Reflectance)`
- `source`: e.g. `Sentinel-2 MSI Level-2A (Copernicus Data Space)`
