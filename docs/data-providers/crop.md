# Crop & Disease Data Strategy

## Crop Classification & Attribution

Crop intelligence in BHOOMI is sourced with explicit attribution:
1. **Farmer Input**: Direct farmer registration of crop, variety, and sowing date. Takes precedence over remote-sensing estimates.
2. **Remote-Sensing Crop Classification**: Optical/SAR crop classification algorithms. Always labeled as `Model-Estimated Crop` with confidence scores.
3. **Approved Agricultural Extension Models**: State university agricultural calendars (e.g. TNAU, UAS Bangalore) for phenological stage estimation based on sowing dates and growing degree days (GDD).

### Farmer Correction
Farmers can review and update model-predicted crop types directly through the farm management UI.

## Disease Diagnosis Strategy
Disease intelligence is fundamentally event-driven:
- **Trigger**: Farmer captures and uploads a plant leaf image or submits symptoms.
- **Processing**: Vision model analyzes crop leaf for biotic/abiotic stress.
- **Persistence**: Diagnosis records image hash, identified condition, confidence level, top-k classes, recommended regenerative practices, and model version.
- **No Idle Polling**: The disease pipeline is NEVER continuously polled or regenerated in the absence of an explicit diagnostic event or farmer request.

## Farm Data Snapshot Before AI
Before calling the BHOOMI AI engine, the system freezes an immutable `FarmDataSnapshot`:
```json
{
  "farm": { "id": "...", "crop": "rice", "crop_stage": "tillering", "area_ha": 3.0 },
  "weather": { "temperature_c": 31.2, "source": "IMD", "observed_at": "..." },
  "soil": { "ph": 6.8, "organic_carbon": 0.55, "source": "Soil Health Card" },
  "satellite": { "ndvi": 0.68, "source": "Sentinel-2", "observed_at": "..." },
  "water": { "stress_level": "low", "irrigation_type": "canal" },
  "disease": { "status": "none_detected" },
  "missing_inputs": []
}
```
The AI reasons over this validated snapshot and records all `source_observations` in the auditable intelligence result. The AI NEVER connects directly to external provider endpoints.
