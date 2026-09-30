export type Role = "farmer" | "agronomist" | "state_admin" | "platform_admin";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  state: string | null;
  preferred_language: string;
}

export interface Farm {
  id: string;
  user_id: string;
  name: string;
  state: string;
  district: string;
  taluk: string | null;
  village: string | null;
  latitude: number;
  longitude: number;
  boundary_geojson: GeoJSON.Geometry | null;
  area_hectares: number;
  soil_type: string | null;
  irrigation_type: string | null;
  water_source: string | null;
  current_crop: string | null;
  crop_variety: string | null;
  crop_stage: string | null;
  sowing_date: string | null;
  previous_crop: string | null;
  created_at: string;
  updated_at: string;
}

export type Severity = "low" | "moderate" | "high" | "critical";

export interface AdvisoryAction {
  title: string;
  priority: string;
  reason: string;
}

export interface EvidenceItem {
  source: string;
  value: string;
  timestamp: string;
}

export interface Advisory {
  id: string;
  farm_id: string;
  type: string;
  severity: Severity;
  title: string;
  summary: string;
  actions: AdvisoryAction[];
  evidence: EvidenceItem[];
  source_references: { source: string; authority: string }[];
  confidence: number;
  generated_by: string;
  review_status: string;
  created_at: string;
}

export interface IntelligenceFactor {
  name: string;
  impact: number;
  detail: string;
}

export interface IntelligenceResponse {
  farm: { id: string; name: string; crop: string | null; crop_stage: string | null; area_hectares: number };
  health: {
    // null when the farm has no measured data; render "Not enough data".
    score: number | null;
    label: string;
    has_data: boolean;
    data_coverage: number;
    missing_inputs: string[];
    climate_risk: Severity | "unknown";
    water_stress: Severity | "unknown";
    disease_risk: Severity | "unknown";
    vegetation_stress: Severity | "unknown";
    soil_health: Severity | "unknown";
    breakdown: Record<string, { weight: number; score: number | null; has_data: boolean }>;
    factors: IntelligenceFactor[];
  };
  weather: {
    temperature_c: number | null;
    humidity_pct: number | null;
    rain_probability_pct: number | null;
    condition: string | null;
    source: string;
    is_stale: boolean;
    observed_at: string | null;
  };
  soil: {
    ph: number | null;
    organic_carbon: number | null;
    nitrogen: number | null;
    phosphorus: number | null;
    potassium: number | null;
    moisture: number | null;
    sample_date: string | null;
    source: string;
  };
  vegetation: {
    ndvi: number | null;
    evi: number | null;
    trend_7d_pct: number | null;
    vegetation_health: string | null;
    observation_date: string | null;
    source: string;
    is_dev_dataset: boolean;
  };
  advisories: Advisory[];
  ai_interpretation: string | null;
  ai_provider_used: string | null;
  ai_is_model_generated?: boolean;
  bhoomi_report?: string | null;
}

export interface DiseaseAnalysisResult {
  scan_id: string;
  crop: string;
  possible_disease: string;
  confidence: number;
  severity: string;
  top_k: { class: string; confidence: number }[];
  recommended_actions: string[];
  limitations: string[];
  is_dev_model: boolean;
  ai_explanation: string | null;
  ai_provider_used: string | null;
}

export interface StateNode {
  id: string;
  state: string;
  node_id: string;
  display_name: string;
  status: string;
  data_policy: string;
  available_models: number;
  supported_crops: string[];
  is_demo: boolean;
  last_sync: string;
}

export interface ModelRegistryEntry {
  id: string;
  name: string;
  description: string;
  publisher_state_node_id: string;
  version: string;
  model_type: string;
  crop: string;
  supported_regions: string[];
  accuracy: number | null;
  training_dataset_description: string;
  license: string;
  visibility: string;
  status: string;
  is_demo: boolean;
  created_at: string;
}

export interface CooperationSummary {
  nodes: { state: string; status: string; is_demo: boolean; last_sync: string }[];
  shared_models: number;
  shared_schemas: number;
  model_requests: number;
}

export interface SoilProfile {
  id: string;
  farm_id: string;
  ph: number | null;
  nitrogen: number | null;
  phosphorus: number | null;
  potassium: number | null;
  organic_carbon: number | null;
  electrical_conductivity: number | null;
  sulfur: number | null;
  zinc: number | null;
  iron: number | null;
  copper: number | null;
  manganese: number | null;
  boron: number | null;
  moisture: number | null;
  source: string;
  sample_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  severity: string;
  read_at: string | null;
  created_at: string;
}

export type FreshnessState = "LIVE" | "RECENT" | "STALE" | "OUTDATED" | "UNKNOWN";

export interface DomainFreshness {
  status: FreshnessState | "DATA NOT AVAILABLE";
  source?: string | null;
  last_updated?: string | null;
  observed_at?: string | null;
  data_age_hours?: number | null;
  count?: number;
}

export interface FarmDataStatusResponse {
  farm_id: string;
  country: string;
  state: string | null;
  domains: {
    weather: DomainFreshness;
    soil: DomainFreshness;
    satellite: DomainFreshness;
    crop: DomainFreshness;
    water: DomainFreshness;
    disease: DomainFreshness;
  };
  overall_freshness: string;
}

export interface WaterMoistureMeasurement {
  value_pct: number | null;
  source?: string | null;
  observed_at?: string | null;
  sampled_at?: string | null;
  freshness?: string | null;
}

export interface FarmWaterIntelligence {
  farm_id?: string;
  soil_moisture_lab?: WaterMoistureMeasurement | null;
  soil_moisture_satellite?: WaterMoistureMeasurement | null;
  soil_moisture_sensor?: WaterMoistureMeasurement | null;
  rainfall_mm?: number | null;
  precipitation_recent_mm?: number | null;
  irrigation_type?: string | null;
  water_source?: string | null;
  water_stress_index?: string | null;
  drought_index?: string | null;
  confidence?: number;
}

export interface SourceProvenanceItem {
  domain: string;
  provider_name: string;
  country: string;
  source_type: string;
  observed_at: string | null;
  freshness: string;
  license: string;
  terms_url: string;
}

export interface FarmSourcesResponse {
  farm_id: string;
  sources: SourceProvenanceItem[];
}

export interface TimelineObservation {
  observed_at: string;
  domain: "satellite" | "weather" | "soil" | string;
  indicator: string;
  value: number | null;
  unit: string;
  source: string;
}

export interface FarmTimelineResponse {
  farm_id: string;
  window: string;
  timeline: TimelineObservation[];
}

export interface ProviderInfo {
  id: string;
  name: string;
  country: string;
  region?: string | null;
  data_type: string;
  status: "healthy" | "degraded" | "auth_required" | "failed" | string;
  auth_status: string;
  priority: number;
  enabled: boolean;
  last_sync: string | null;
  next_sync?: string | null;
  refresh_interval_minutes?: number;
  error_message?: string | null;
}

export interface ProviderSyncRunItem {
  id: string;
  provider_id: string;
  trigger_type: string;
  status: string;
  records_ingested: number;
  duration_ms: number;
  started_at: string | null;
}

export interface ProviderRegistryStatusResponse {
  summary: {
    total_providers: number;
    healthy: number;
    degraded: number;
    failed: number;
    /** Providers proven reachable by this deployment. */
    connected: number;
    /** Declared in the registry but not proven reachable. */
    unverified: number;
    last_sync: string | null;
  };
  providers: ProviderInfo[];
  recent_sync_runs: ProviderSyncRunItem[];
}

export interface CountryProviderMapItem {
  country: string;
  has_national_weather: boolean;
  has_national_soil: boolean;
  has_national_satellite: boolean;
  regions: {
    region: string;
    weather: boolean;
    soil: boolean;
    satellite: boolean;
  }[];
}

