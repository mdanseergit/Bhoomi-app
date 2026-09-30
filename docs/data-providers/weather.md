# Weather & Climate Provider Architecture

## Architecture & Provider Hierarchy

BHOOMI resolves weather providers using a hierarchical fallback order:
```
           Farm Geolocation (Lat, Lon)
                       │
                       ▼
             Country & State Resolver
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
1. National Official         2. Global Fallback
   (e.g., IMD for India)        (NASA POWER)
         │                           │
         │ (if unavailable)          │
         └─────────────►─────────────┘
                       │
                       ▼
               3. Local Cached Snapshot
                  (marked STALE)
```

## Freshness & Frequency Principles
Weather has a natural update cadence of 15 to 60 minutes for current observations, and 6 to 12 hours for numerical weather prediction forecasts.

| Freshness Status | Age Threshold | Description |
|---|---|---|
| `LIVE` | < 1 hour | Active telemetry observation from verified station or radar |
| `RECENT` | 1–3 hours | Fresh observation within standard atmospheric update window |
| `STALE` | 3–24 hours | Delayed telemetry; fallback warning displayed |
| `OUTDATED` | > 24 hours | Historical baseline only; not used for active irrigation advice |

## Canonical Schema Mapping
All providers transform into `CanonicalWeather`:
- `temperature_c`: Normalized to degrees Celsius
- `humidity_pct`: Normalized to percentage (0–100%)
- `rainfall_mm`: Normalized to millimeters
- `rain_probability_pct`: Normalized to percentage (0–100%)
- `wind_speed_mps`: Normalized to meters per second (internal unit)

## Automatic Failover Behavior
When the primary national weather provider encounters an HTTP 5xx, timeout, or authentication error:
1. Provider status is transitioned to `degraded`.
2. BHOOMI falls back to `NASA POWER`.
3. The observation record stores `source = "NASA POWER (Fallback)"`.
4. The UI prominently displays the fallback source. Under no circumstances is fallback data presented as the primary official national source.
