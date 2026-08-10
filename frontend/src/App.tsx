import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';
import { api } from './api';
import type {
  LocationConfig, ManualWeather, ManualYolo, PipelineResult, ImageryData, HistoryPoint,
} from './api';

import Sidebar            from './components/Sidebar';
import PHRIGauge          from './components/PHRIGauge';
import MetricCard         from './components/MetricCard';
import SatellitePanel     from './components/SatellitePanel';
import SEIRChart          from './components/SEIRChart';
import WeatherRadar       from './components/WeatherRadar';
import HistoricalTimeline from './components/HistoricalTimeline';
import HealthBulletin     from './components/HealthBulletin';
import ActionItems        from './components/ActionItems';
import StressTest         from './components/StressTest';
import LoadingOverlay     from './components/LoadingOverlay';
import LandingPage        from './components/LandingPage';

// ── Defaults ─────────────────────────────────────────────────────────────────
const DEFAULT_LOCATION: LocationConfig = {
  lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka',
};
const DEFAULT_WEATHER: ManualWeather = {
  temperature_2m_c: 26.0, relative_humidity_pct: 72.0, precipitation_imerg_mm: 8.0,
  dew_frost_point_c: 18.0, wind_speed_10m_ms: 2.5, all_sky_insolation_clearness: 0.5,
};
const DEFAULT_YOLO: ManualYolo = {
  stagnant_water_count: 0, stagnant_water_area_px: 0,
  garbage_count: 0, vegetation_anomaly_score: 0.1,
};

function phriColor(s: number): string {
  if (s < 0.40) return 'var(--green)';
  if (s < 0.60) return 'var(--amber)';
  if (s < 0.75) return '#f97316';
  return 'var(--red)';
}

type View = 'landing' | 'surveillance' | 'stress';
type Theme = 'dark' | 'light';

export default function App() {
  const [theme, setTheme]         = useState<Theme>('dark');
  const [view, setView]           = useState<View>('landing');
  const [panelOpen, setPanelOpen] = useState(true);

  const [mode,        setMode       ] = useState('live');
  const [location,    setLocation   ] = useState<LocationConfig>(DEFAULT_LOCATION);
  const [weather,     setWeather    ] = useState<ManualWeather>(DEFAULT_WEATHER);
  const [yolo,        setYolo       ] = useState<ManualYolo>(DEFAULT_YOLO);
  const [histDate,    setHistDate   ] = useState('2024-08-15');
  const [yoloEnabled, setYoloEnabled] = useState(false);

  const [result,    setResult   ] = useState<PipelineResult | null>(null);
  const [imagery,   setImagery  ] = useState<ImageryData | null>(null);
  const [history,   setHistory  ] = useState<HistoryPoint[]>([]);
  const [isProxy,   setIsProxy  ] = useState(true);
  const [loading,   setLoading  ] = useState(false);
  const [loadStep,  setLoadStep ] = useState(0);
  const [error,     setError    ] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  // Apply theme class
  useEffect(() => {
    document.documentElement.classList.toggle('light-mode', theme === 'light');
  }, [theme]);

  // Check backend on mount
  useEffect(() => {
    api.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false));
    api.imagery().then(setImagery).catch(() => {});
    api.history().then(r => {
      setHistory(r.data);
      setIsProxy(r.is_proxy ?? true);
    }).catch(() => {});
  }, []);

  // Run pipeline
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
        if (res.rgb_b64 || res.ndwi_b64) {
          setImagery({ rgb_b64: res.rgb_b64 ?? null, ndwi_b64: res.ndwi_b64 ?? null, meta: res.live_meta ?? null });
        }
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

  const handleLaunchCity = (city: LocationConfig) => {
    setLocation(city);
    setResult(null);
    setError(null);
    setMode('live');
    setView('surveillance');
  };

  const score     = result?.phri.score ?? 0;
  const riskLevel = result?.phri.risk_level ?? 'LOW';
  const color     = phriColor(score);
  const today     = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <>
      <LoadingOverlay visible={loading} step={loadStep} />

      <div className={`app-shell ${theme === 'light' ? 'light-mode' : ''}`}>

        {/* ── Top Navigation Bar ─────────────────────────────────────────── */}
        <nav className="top-nav">
          <div className="top-nav-logo" onClick={() => setView('landing')}>
            <span>🛰️</span>
            Sentin-AI
          </div>

          <div className="top-nav-links">
            <button
              className={`top-nav-link ${view === 'landing' ? 'active' : ''}`}
              onClick={() => setView('landing')}
              style={{ position: 'relative' }}
            >
              <span style={{ position: 'relative', zIndex: 1 }}>🏠 Overview</span>
              {view === 'landing' && (
                <motion.div
                  layoutId="activeNavTabUnderline"
                  style={{
                    position: 'absolute',
                    bottom: -1,
                    left: 0,
                    right: 0,
                    height: 2,
                    background: 'var(--cyan)',
                    zIndex: 2
                  }}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
            <button
              className={`top-nav-link ${view === 'surveillance' ? 'active' : ''}`}
              onClick={() => setView('surveillance')}
              style={{ position: 'relative' }}
            >
              <span style={{ position: 'relative', zIndex: 1 }}>📡 Surveillance Hub</span>
              {view === 'surveillance' && (
                <motion.div
                  layoutId="activeNavTabUnderline"
                  style={{
                    position: 'absolute',
                    bottom: -1,
                    left: 0,
                    right: 0,
                    height: 2,
                    background: 'var(--cyan)',
                    zIndex: 2
                  }}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
            <button
              className={`top-nav-link ${view === 'stress' ? 'active' : ''}`}
              onClick={() => setView('stress')}
              style={{ position: 'relative' }}
            >
              <span style={{ position: 'relative', zIndex: 1 }}>🧪 Stress Simulation</span>
              {view === 'stress' && (
                <motion.div
                  layoutId="activeNavTabUnderline"
                  style={{
                    position: 'absolute',
                    bottom: -1,
                    left: 0,
                    right: 0,
                    height: 2,
                    background: 'var(--cyan)',
                    zIndex: 2
                  }}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
          </div>

          <div className="nav-actions">
            {/* Backend status pill */}
            {backendOk !== null && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                background: backendOk ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${backendOk ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
                borderRadius: 20, padding: '0.25rem 0.75rem',
                fontSize: '0.72rem', fontFamily: 'DM Mono', color: backendOk ? 'var(--green)' : 'var(--red)',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: backendOk ? 'var(--green)' : 'var(--red)',
                }} />
                API {backendOk ? 'Online' : 'Offline'}
              </div>
            )}

            {/* Theme toggle */}
            <button
              className="theme-toggle-btn"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </nav>

        {/* ── Content ────────────────────────────────────────────────────── */}
        <div className="content-wrapper">
          <AnimatePresence mode="wait">

            {/* ── Landing View ── */}
            {view === 'landing' && (
              <motion.div
                key="landing"
                style={{ flex: 1, display: 'flex', width: '100%' }}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <LandingPage
                  theme={theme}
                  onStartSurveillance={handleLaunchCity}
                  onNavigateToStress={() => setView('stress')}
                />
              </motion.div>
            )}

            {/* ── Stress Test View ── */}
            {view === 'stress' && (
              <motion.div
                key="stress"
                style={{ flex: 1, padding: '1.5rem 2rem', overflowY: 'auto' }}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <div style={{ maxWidth: 900, margin: '0 auto' }}>
                  <div style={{ marginBottom: '1.25rem' }}>
                    <h2 style={{ fontSize: '1.25rem' }}>Stress Simulation</h2>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Sweep PHRI scores across disease buckets to evaluate model sensitivity and alert thresholds.
                    </p>
                  </div>
                  <StressTest />
                </div>
              </motion.div>
            )}

            {/* ── Surveillance Hub View ── */}
            {view === 'surveillance' && (
              <motion.div
                key="surveillance"
                className="surveillance-layout"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                {/* Collapsible Options Drawer */}
                <div className={`options-panel ${panelOpen ? '' : 'collapsed'}`}>
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
                </div>

                {/* Main Workspace */}
                <div className="workspace-panel">
                  <div className="panel-toggle-bar">
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                      onClick={() => setPanelOpen(o => !o)}
                    >
                      {panelOpen ? '◀ Hide Panel' : '▶ Show Panel'}
                    </button>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'DM Mono' }}>
                      {location.location_name} · {today}
                    </span>
                  </div>

                  {/* Error */}
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{
                        background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
                        borderRadius: 8, padding: '0.9rem 1.1rem', marginBottom: '1rem',
                        fontFamily: 'DM Mono', fontSize: '0.8rem', color: 'var(--red)',
                      }}
                    >
                      ⚠️ {error.split('\n')[0]}
                    </motion.div>
                  )}

                  {/* Empty state */}
                  {!result && !loading && (
                    <div className="empty-state fade-up">
                      <div className="empty-icon">🛰️</div>
                      <div className="empty-title">Sentin-AI Ready</div>
                      <div className="empty-sub">
                        {mode === 'live'
                          ? 'Click ⚡ Execute Live Pipeline to fetch satellite data.'
                          : mode === 'manual'
                          ? 'Configure weather parameters, then click ▶ Run Analysis.'
                          : 'Select a date and click ▶ Run Analysis to score that day.'}
                      </div>
                    </div>
                  )}

                  {/* Results */}
                  <AnimatePresence>
                    {result && (
                      <motion.div
                        key="results"
                        initial="hidden"
                        animate="show"
                        variants={{
                          hidden: { opacity: 0 },
                          show: {
                            opacity: 1,
                            transition: { staggerChildren: 0.06, delayChildren: 0.05 }
                          }
                        }}
                      >
                        {/* ── Risk Assessment ── */}
                        <motion.div
                          variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } }}
                        >
                          <div className="section-label">Risk Assessment</div>
                          <div className="grid-5" style={{ marginBottom: '1.25rem' }}>
                            <PHRIGauge score={score} riskLevel={riskLevel} />
                            <MetricCard title="Disease Risk" value={result.disease.label}
                              sub={result.disease.primary_bucket.replace(/_/g, ' ')} color={color} delay={0.06} />
                            <MetricCard title="Peak Cases" value={result.seir.peak_cases}
                              sub={`Day ${result.seir.peak_day} of ${result.seir.projection_days}`}
                              color={color} delay={0.12} numeric />
                            <MetricCard title="14-Day Total" value={result.seir.total_projected}
                              sub={`Attack rate ${result.seir.attack_rate_pct.toFixed(3)}%`}
                              color={color} delay={0.18} numeric />
                            <MetricCard title="Confidence"
                              value={`${(result.phri.confidence * 100).toFixed(0)}%`}
                              sub={result.phri.visual_complete ? '✅ Visual + Weather' : '🌡️ Weather only'}
                              color="var(--cyan)" delay={0.24} />
                          </div>
                        </motion.div>

                        {/* ── Satellite Layer ── */}
                        <motion.div
                          variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } }}
                        >
                          <div className="section-label" style={{ marginTop: '0.5rem' }}>
                            Satellite Perception Layer (Sentinel-2 {location.radius_km}km ROI)
                          </div>
                          <div style={{ marginBottom: '1.25rem' }}>
                            <SatellitePanel
                              rgbB64={result.rgb_b64 ?? imagery?.rgb_b64 ?? null}
                              ndwiB64={result.ndwi_b64 ?? imagery?.ndwi_b64 ?? null}
                              meta={result.live_meta ?? imagery?.meta ?? null}
                              locationName={location.location_name}
                              lat={location.lat} lon={location.lon} radiusKm={location.radius_km}
                            />
                          </div>
                        </motion.div>

                        {/* ── Projection & Environment ── */}
                        <motion.div
                          variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } }}
                        >
                          <div className="section-label">Projection &amp; Environment</div>
                          <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
                            <SEIRChart
                              newCasesCurve={result.seir.new_cases_curve}
                              peakCases={result.seir.peak_cases}
                              peakDay={result.seir.peak_day}
                              totalProjected={result.seir.total_projected}
                              diseaseLabel={result.seir.disease_label}
                              phriScore={score}
                            />
                            <WeatherRadar weather={result.weather} />
                          </div>
                        </motion.div>

                        {/* ── Historical Timeline ── */}
                        {history.length > 0 && (
                          <motion.div
                            variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } }}
                          >
                            <div className="section-label">Historical Risk Timeline</div>
                            <div style={{ marginBottom: '1.25rem' }}>
                              <HistoricalTimeline data={history} isProxy={isProxy} />
                            </div>
                          </motion.div>
                        )}

                        {/* ── Health Bulletin ── */}
                        <motion.div
                          variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } }}
                        >
                          <div className="section-label">Health Bulletin</div>
                          <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
                            <HealthBulletin bulletin={result.bulletin} />
                            <ActionItems disease={result.disease} actionItems={result.bulletin.action_items} />
                          </div>
                        </motion.div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Historical timeline when no result yet */}
                  {!result && !loading && history.length > 0 && (
                    <div style={{ marginTop: '1rem' }}>
                      <div className="section-label">Historical Risk Timeline (2023–2024)</div>
                      <HistoricalTimeline data={history} isProxy={isProxy} />
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </>
  );
}
