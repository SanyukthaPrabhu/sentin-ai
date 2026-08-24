// API base URL
const BASE = 'http://localhost:8000';

export interface LocationConfig {
  lat: number;
  lon: number;
  radius_km: number;
  location_name: string;
}

export interface ManualWeather {
  temperature_2m_c: number;
  relative_humidity_pct: number;
  precipitation_imerg_mm: number;
  dew_frost_point_c: number;
  wind_speed_10m_ms: number;
  all_sky_insolation_clearness: number;
}

export interface ManualYolo {
  stagnant_water_count: number;
  stagnant_water_area_px: number;
  garbage_count: number;
  vegetation_anomaly_score: number;
}

export interface PHRIData {
  score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  visual_complete: boolean;
}

export interface DiseaseData {
  primary_bucket: string;
  label: string;
  vector: string;
  warning_signs: string;
  prevention: string;
  incubation_days: string;
  secondary_buckets: string[];
  rules_triggered: string[];
}

export interface SEIRData {
  disease_label: string;
  peak_cases: number;
  peak_day: number;
  total_projected: number;
  attack_rate_pct: number;
  beta_effective: number;
  projection_days: number;
  new_cases_curve: number[];
  population: number;
}

export interface BulletinData {
  headline: string;
  health_bulletin: string;
  action_items: string[];
  officer_note: string;
  fallback_used: boolean;
  generated_date: string;
}

export interface LiveMeta {
  source?: string;
  date: string;
  cloud_pct: string | number;
  ndwi_mean: string | number;
  ndvi_mean: string | number;
}

export interface PipelineResult {
  phri: PHRIData;
  disease: DiseaseData;
  seir: SEIRData;
  bulletin: BulletinData;
  weather: Partial<ManualWeather>;
  yolo: Partial<ManualYolo>;
  location_name: string;
  live_meta?: LiveMeta;
  rgb_b64?: string | null;
  ndwi_b64?: string | null;
  demo_mode?: boolean;
}

export interface ImageryData {
  rgb_b64: string | null;
  ndwi_b64: string | null;
  meta: LiveMeta | null;
}

export interface HistoryPoint {
  date: string;
  phri: number;
  temp: number;
  rain: number;
  humid: number;
}

export interface StressTestData {
  disease_bucket: string;
  disease_label: string;
  phri_values: number[];
  total_cases: number[];
  peak_cases: number[];
  available_buckets: string[];
}

export interface AlertItem {
  id: number;
  location: string;
  latitude: number;
  longitude: number;
  title: string;
  message: string;
  severity: 'MODERATE' | 'HIGH' | 'CRITICAL';
  phri_score?: number;
  source: string;
  source_type: 'ai' | 'official';
  created_at: string;
  expires_at?: string;
}

export interface SubscriptionRequest {
  email?: string;
  phone?: string;
  location_name: string;
  latitude: number;
  longitude: number;
  all_alerts: boolean;
  environmental_alerts: boolean;
  disease_risk_alerts: boolean;
  weather_alerts: boolean;
  official_disaster_alerts: boolean;
  severity_preference: 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface AwarenessGuide {
  id: number;
  category: string;
  title: string;
  description: string;
  created_at: string;
}

export interface MapMarker {
  type: 'ai_risk' | 'official_alert';
  name: string;
  lat: number;
  lon: number;
  phri?: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'MODERATE';
  disease?: string;
  message?: string;
  source?: string;
  updated_at: string;
}

export interface AdminSystemData {
  monitored_locations_count: number;
  monitored_locations: {
    name: string;
    latitude: number;
    longitude: number;
    radius_km: number;
    created_at: string;
  }[];
  subscriptions_count: number;
  active_ai_alerts: number;
  active_official_alerts: number;
  failed_fetches_count: number;
  system_health: {
    database: string;
    model: string;
    weather_api: string;
    earth_engine: string;
    groq_llm: string;
    notification_service: string;
  };
  demo_mode: string | null;
}

export interface SystemLog {
  id: number;
  timestamp: string;
  request_id?: string;
  location?: string;
  stage?: string;
  model_inference_time_ms?: number;
  api_latency_ms?: number;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
  error_details?: string;
}

// ── API calls ────────────────────────────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export const api = {
  health: () => get<{ status: string }>('/api/health'),

  manual: (location: LocationConfig, weather: ManualWeather, yolo: ManualYolo) =>
    post<PipelineResult>('/api/pipeline/manual', { location, weather, yolo }),

  live: (location: LocationConfig) =>
    post<PipelineResult>('/api/pipeline/live', { location }),

  historical: (location: LocationConfig, hist_date: string) =>
    post<PipelineResult>('/api/pipeline/historical', { location, hist_date }),

  stressTest: (disease_bucket: string) =>
    post<StressTestData>('/api/pipeline/stress-test', { disease_bucket }),

  imagery: () => get<ImageryData>('/api/imagery/latest'),

  history: (lat?: number, lon?: number) =>
    get<{ data: HistoryPoint[]; is_proxy: boolean }>(
      lat !== undefined && lon !== undefined
        ? `/api/history?lat=${lat}&lon=${lon}`
        : '/api/history'
    ),

  // ── Extended Platform APIs ─────────────────────────────────────────────────
  getRiskLocation: (location: string) =>
    get<PipelineResult | { error: string }>(`/api/risk/${encodeURIComponent(location)}`),

  getRiskLatest: () =>
    get<any[]>(`/api/risk/latest`),

  getMapRisk: () =>
    get<MapMarker[]>('/api/map/risk'),

  getAlerts: () =>
    get<{ ai_alerts: AlertItem[]; official_alerts: AlertItem[]; total_active: number }>('/api/alerts'),

  getOfficialAlerts: (location?: string) =>
    get<AlertItem[]>(location ? `/api/alerts/official?location=${encodeURIComponent(location)}` : '/api/alerts/official'),

  getAIAlerts: () =>
    get<AlertItem[]>('/api/alerts/ai'),

  subscribe: (req: SubscriptionRequest) =>
    post<{ status: string; subscription_id: number }>('/api/subscriptions', req),

  unsubscribe: (id: number) =>
    del<{ status: string; id: number }>(`/api/subscriptions/${id}`),

  getAwareness: () =>
    get<AwarenessGuide[]>('/api/awareness'),

  getAwarenessCategory: (category: string) =>
    get<AwarenessGuide>(`/api/awareness/${category}`),

  getEnvironmentHistory: (location: string) =>
    get<any[]>(`/api/environment/${encodeURIComponent(location)}`),

  // Demo Scenarios Control
  setDemoScenario: (scenario: string | null) =>
    post<{ status: string; scenario?: string; message: string }>('/api/pipeline/demo', { scenario: scenario || 'none' }),

  // Admin Controls
  getAdminSystem: () =>
    get<AdminSystemData>('/api/admin/system'),

  getAdminLogs: (limit?: number) =>
    get<SystemLog[]>(limit ? `/api/admin/logs?limit=${limit}` : '/api/admin/logs'),

  addMonitoredLocation: (req: { name: string; latitude: number; longitude: number; radius_km: number }) =>
    post<{ status: string; message: string }>('/api/admin/locations', req),

  getMonitoredLocations: () =>
    get<any[]>('/api/admin/locations'),

  injectOfficialAlert: (req: { title: string; message: string; severity: string; location: string; latitude?: number; longitude?: number; source: string }) =>
    post<{ status: string; message: string }>('/api/admin/alerts/official', req),
};
