import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';
import { api } from './api';
import type {
  LocationConfig, ManualWeather, ManualYolo, PipelineResult, ImageryData, HistoryPoint,
} from './api';

import Sidebar          from './components/Sidebar';
import PHRIGauge        from './components/PHRIGauge';
import MetricCard       from './components/MetricCard';
import SatellitePanel   from './components/SatellitePanel';
import SEIRChart        from './components/SEIRChart';
import WeatherRadar     from './components/WeatherRadar';
import HistoricalTimeline from './components/HistoricalTimeline';
import HealthBulletin   from './components/HealthBulletin';
import ActionItems      from './components/ActionItems';
import StressTest       from './components/StressTest';
import LoadingOverlay   from './components/LoadingOverlay';

// ── Defaults ─────────────────────────────────────────────────────────────────
const DEFAULT_LOCATION: LocationConfig = {
  lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka',
};

const DEFAULT_WEATHER: ManualWeather = {
  temperature_2m_c:             26.0,
  relative_humidity_pct:        72.0,
  precipitation_imerg_mm:       8.0,
  dew_frost_point_c:            18.0,
  wind_speed_10m_ms:            2.5,
  all_sky_insolation_clearness: 0.5,
};

const DEFAULT_YOLO: ManualYolo = {
  stagnant_water_count:     0,
  stagnant_water_area_px:   0,
  garbage_count:             0,
  vegetation_anomaly_score:  0.1,
};

function phriColor(s: number): string {
  if (s < 0.40) return '#00e676';
  if (s < 0.60) return '#ffb300';
  if (s < 0.75) return '#ff6400';
  return '#ff4c4c';
}

export default function App() {
  const [mode,        setMode       ] = useState('live');
  const [location,    setLocation   ] = useState<LocationConfig>(DEFAULT_LOCATION);
  const [weather,     setWeather    ] = useState<ManualWeather>(DEFAULT_WEATHER);
  const [yolo,        setYolo       ] = useState<ManualYolo>(DEFAULT_YOLO);
  const [histDate,    setHistDate   ] = useState('2024-08-15');
  const [yoloEnabled, setYoloEnabled] = useState(false);

  const [result,   setResult  ] = useState<PipelineResult | null>(null);
  const [imagery,  setImagery ] = useState<ImageryData | null>(null);
  const [history,  setHistory ] = useState<HistoryPoint[]>([]);
  const [loading,  setLoading ] = useState(false);
  const [loadStep, setLoadStep] = useState(0);
  const [error,    setError   ] = useState<string | null>(null);
  const [backendOk,setBackendOk] = useState<boolean | null>(null);

  // ── Check backend on mount ───────────────────────────────────────────────
  useEffect(() => {
    api.health()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));

    api.imagery().then(setImagery).catch(() => {});
    api.history().then(r => setHistory(r.data)).catch(() => {});
  }, []);

  // ── Run pipeline ──────────────────────────────────────────────────────────
  const handleRun = async () => {
    setError(null);
    setLoading(true);
    setLoadStep(0);

    try {
      let res: PipelineResult;

      if (mode === 'live') {
        setLoadStep(0); await new Promise(r => setTimeout(r, 400));
        setLoadStep(1); await new Promise(r => setTimeout(r, 400));
        setLoadStep(2); await new Promise(r => setTimeout(r, 300));
        setLoadStep(3);
        res = await api.live(location);
        setLoadStep(4);
        // Refresh imagery after live run
        api.imagery().then(setImagery).catch(() => {});
      } else if (mode === 'manual') {
        setLoadStep(3);
        res = await api.manual(location, weather, yoloEnabled ? yolo : DEFAULT_YOLO);
        setLoadStep(4);
      } else if (mode === 'historical') {
        setLoadStep(3);
        res = await api.historical(location, histDate);
        setLoadStep(4);
      } else {
        setLoading(false);
        return;
      }

      setResult(res);
    } catch (e: any) {
      setError(e.message || 'Pipeline error');
    } finally {
      setLoading(false);
    }
  };

  const score      = result?.phri.score ?? 0;
  const riskLevel  = result?.phri.risk_level ?? 'LOW';
  const color      = phriColor(score);
  const today      = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <>
      <LoadingOverlay visible={loading} step={loadStep} />

      <div className="app-shell">
        {/* ── Sidebar ──────────────────────────────────────────────────────── */}
        <Sidebar
          mode={mode} location={location} weather={weather}
          yolo={yolo} histDate={histDate} yoloEnabled={yoloEnabled}
          onModeChange={m => { setMode(m); setResult(null); setError(null); }}
          onLocationChange={l => { setLocation(l); setResult(null); }}
          onWeatherChange={setWeather}
          onYoloChange={setYolo}
          onHistDateChange={setHistDate}
          onYoloToggle={setYoloEnabled}
          onRun={handleRun}
          loading={loading}
        />

        {/* ── Main ─────────────────────────────────────────────────────────── */}
        <main className="main-content">
          {/* Hero */}
          <div className="hero shimmer">
            <div className="hero-title">🛰️ Sentin-AI</div>
            <div className="hero-sub">
              AI-Powered Proactive Disease Outbreak Monitor &nbsp;·&nbsp;
              {location.location_name} ({location.lat}°N, {location.lon}°E) &nbsp;·&nbsp;
              {today}
            </div>
            {/* Backend status */}
            <div style={{ position: 'absolute', top: '1rem', right: '1.25rem', display: 'flex',
              alignItems: 'center', gap: '0.5rem' }}>
              {backendOk !== null && (
                <>
                  <div className={backendOk ? 'ping-dot' : ''} style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: backendOk ? '#00e676' : '#ff4c4c',
                  }} />
                  <span style={{ fontFamily: 'DM Mono', fontSize: '0.7rem', color: '#6b7a99' }}>
                    API {backendOk ? 'Online' : 'Offline'}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Stress Test mode — standalone */}
          {mode === 'stress' && <StressTest />}

          {/* Error banner */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ background: 'rgba(255,76,76,0.08)', border: '1px solid rgba(255,76,76,0.3)',
                borderRadius: 12, padding: '1rem 1.25rem', marginBottom: '1rem',
                fontFamily: 'DM Mono', fontSize: '0.82rem', color: '#ff4c4c' }}
            >
              ⚠️ {error.split('\n')[0]}
            </motion.div>
          )}

          {/* Empty state */}
          {mode !== 'stress' && !result && !loading && (
            <div className="empty-state fade-up">
              <div className="empty-icon">🛰️</div>
              <div className="empty-title">Sentin-AI Ready</div>
              <div className="empty-sub">
                {mode === 'live'
                  ? 'Click ⚡ Execute Live Pipeline in the sidebar to fetch live satellite data.'
                  : mode === 'manual'
                  ? 'Configure weather parameters in the sidebar, then click ▶ Run Analysis.'
                  : 'Select a date and click ▶ Run Analysis to score that historical day.'}
              </div>
            </div>
          )}

          {/* ── Results ────────────────────────────────────────────────────── */}
          <AnimatePresence>
          {result && mode !== 'stress' && (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
            >
              {/* Row 1: PHRI + Metrics */}
              <div className="section-label">Risk Assessment</div>
              <div className="grid-5" style={{ marginBottom: '1.25rem' }}>
                <PHRIGauge score={score} riskLevel={riskLevel} />
                <MetricCard
                  title="Disease Risk"
                  value={result.disease.label}
                  sub={result.disease.primary_bucket.replace(/_/g, ' ')}
                  color={color}
                  delay={0.06}
                />
                <MetricCard
                  title="Peak Cases"
                  value={result.seir.peak_cases}
                  sub={`Day ${result.seir.peak_day} of ${result.seir.projection_days}`}
                  color={color}
                  delay={0.12}
                  numeric
                />
                <MetricCard
                  title="14-Day Total"
                  value={result.seir.total_projected}
                  sub={`Attack rate ${result.seir.attack_rate_pct.toFixed(3)}%`}
                  color={color}
                  delay={0.18}
                  numeric
                />
                <MetricCard
                  title="Confidence"
                  value={`${(result.phri.confidence * 100).toFixed(0)}%`}
                  sub={result.phri.visual_complete ? '✅ Visual + Weather' : '🌡️ Weather only'}
                  color="#00e5ff"
                  delay={0.24}
                />
              </div>

              {/* Row 2: Satellite */}
              <div className="section-label" style={{ marginTop: '0.5rem' }}>
                Satellite Perception Layer (Sentinel-2 {location.radius_km}km ROI)
              </div>
              <div style={{ marginBottom: '1.25rem' }}>
                <SatellitePanel
                  rgbB64={imagery?.rgb_b64 ?? null}
                  ndwiB64={imagery?.ndwi_b64 ?? null}
                  meta={result.live_meta ?? imagery?.meta ?? null}
                  locationName={location.location_name}
                  lat={location.lat}
                  lon={location.lon}
                  radiusKm={location.radius_km}
                />
              </div>

              {/* Row 3: SEIR + Weather Radar */}
              <div className="section-label">Projection & Environment</div>
              <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
                <div style={{ gridColumn: 'span 1' }}>
                  <SEIRChart
                    newCasesCurve={result.seir.new_cases_curve}
                    peakCases={result.seir.peak_cases}
                    peakDay={result.seir.peak_day}
                    totalProjected={result.seir.total_projected}
                    diseaseLabel={result.seir.disease_label}
                    phriScore={score}
                  />
                </div>
                <WeatherRadar weather={result.weather} />
              </div>

              {/* Row 4: Historical Timeline */}
              {history.length > 0 && (
                <>
                  <div className="section-label">Historical Risk Timeline</div>
                  <div style={{ marginBottom: '1.25rem' }}>
                    <HistoricalTimeline data={history} />
                  </div>
                </>
              )}

              {/* Row 5: Bulletin + Actions */}
              <div className="section-label">Health Bulletin</div>
              <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
                <HealthBulletin bulletin={result.bulletin} />
                <ActionItems disease={result.disease} actionItems={result.bulletin.action_items} />
              </div>
            </motion.div>
          )}
          </AnimatePresence>

          {/* Historical timeline always shown at bottom */}
          {mode !== 'stress' && !result && history.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div className="section-label">Historical Risk Timeline (2023–2024)</div>
              <HistoricalTimeline data={history} />
            </div>
          )}
        </main>
      </div>
    </>
  );
}
