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
  rgb_b64?: string | null;    // per-location image, only on live runs
  ndwi_b64?: string | null;   // per-location NDWI,  only on live runs
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
};
