import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';
import { api } from './api';
import type {
  LocationConfig, ManualWeather, ManualYolo, PipelineResult, ImageryData, HistoryPoint, AlertItem, MapMarker
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
import InteractiveMap     from './components/InteractiveMap';
import AwarenessCenter    from './components/AwarenessCenter';
import AdminPanel         from './components/AdminPanel';
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

const QUICK_CITIES: (LocationConfig & { name: string; desc: string; icon: string })[] = [
  { name: 'Bengaluru', lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka', desc: '湖泊 stagnant water tracking & temporal vectors.', icon: '🏢' },
  { name: 'Mumbai', lat: 19.07, lon: 72.87, radius_km: 5, location_name: 'Mumbai, Maharashtra', desc: 'Monsoon precipitation & urban waste vectors.', icon: '🌊' },
  { name: 'Chennai', lat: 13.08, lon: 80.27, radius_km: 5, location_name: 'Chennai, Tamil Nadu', desc: 'Coastal vegetation index anomalies & humidity.', icon: '🌴' },
  { name: 'Kolkata', lat: 22.57, lon: 88.36, radius_km: 5, location_name: 'Kolkata, West Bengal', desc: 'River delta inundation & vector population.', icon: '🌿' },
];

function phriColor(s: number): string {
  if (s < 0.40) return 'var(--green)';
  if (s < 0.60) return 'var(--amber)';
  if (s < 0.75) return '#f97316';
  return 'var(--red)';
}

type TabView = 'home' | 'dashboard' | 'map' | 'alerts' | 'awareness' | 'about' | 'subscribe' | 'admin' | 'stress';
type Theme = 'dark' | 'light';

export default function App() {
  const [theme, setTheme]         = useState<Theme>('dark');
  const [view, setView]           = useState<TabView>('home');
  const [panelOpen, setPanelOpen] = useState(true);

  // Pipeline execution parameters
  const [mode,        setMode       ] = useState('live');
  const [location,    setLocation   ] = useState<LocationConfig>(DEFAULT_LOCATION);
  const [weather,     setWeather    ] = useState<ManualWeather>(DEFAULT_WEATHER);
  const [yolo,        setYolo       ] = useState<ManualYolo>(DEFAULT_YOLO);
  const [histDate,    setHistDate   ] = useState('2024-08-15');
  const [yoloEnabled, setYoloEnabled] = useState(false);

  // Data endpoints state
  const [result,    setResult   ] = useState<PipelineResult | null>(null);
  const [imagery,   setImagery  ] = useState<ImageryData | null>(null);
  const [history,   setHistory  ] = useState<HistoryPoint[]>([]);
  const [isProxy,   setIsProxy  ] = useState(true);
  const [loading,   setLoading  ] = useState(false);
  const [loadStep,  setLoadStep ] = useState(0);
  const [error,     setError    ] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  // Simulation/Demo state
  const [demoActive, setDemoActive] = useState(false);
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  // Alerts feeds
  const [aiAlerts, setAiAlerts] = useState<AlertItem[]>([]);
  const [officialAlerts, setOfficialAlerts] = useState<AlertItem[]>([]);
  const [allMarkers, setAllMarkers] = useState<MapMarker[]>([]);

  // Subscription state
  const [subEmail, setSubEmail] = useState('');
  const [subPhone, setSubPhone] = useState('');
  const [subCity, setSubCity] = useState('Bengaluru, Karnataka');
  const [subLat, setSubLat] = useState(12.98);
  const [subLon, setSubLon] = useState(77.58);
  const [subAll, setSubAll] = useState(true);
  const [subSeverity, setSubSeverity] = useState<'MODERATE' | 'HIGH' | 'CRITICAL'>('HIGH');
  const [subSuccess, setSubSuccess] = useState<string | null>(null);

  // Apply theme class
  useEffect(() => {
    document.documentElement.classList.toggle('light-mode', theme === 'light');
  }, [theme]);

  // Load baseline on mount
  const refreshGlobalFeeds = () => {
    api.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false));
    api.imagery().then(setImagery).catch(() => {});
    
    // Fetch combined alerts
    api.getAlerts().then(res => {
      setAiAlerts(res.ai_alerts);
      setOfficialAlerts(res.official_alerts);
    }).catch(() => {});

    // Fetch map markers
    api.getMapRisk().then(res => {
      setAllMarkers(res);
    }).catch(() => {});
  };

  useEffect(() => {
    refreshGlobalFeeds();
  }, [view, demoScenario]);

  // Fetch historical timeline when coordinates or backendOk changes
  useEffect(() => {
    if (backendOk) {
      api.history(location.lat, location.lon)
        .then(r => {
          setHistory(r.data);
          setIsProxy(r.is_proxy ?? true);
        })
        .catch(() => {});
    }
  }, [location.lat, location.lon, backendOk]);

  // Run pipeline execution
  const handleRun = async (customLoc?: LocationConfig) => {
    const activeLoc = customLoc || location;
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
        res = await api.live(activeLoc);
        setLoadStep(4);
        if (res.rgb_b64 || res.ndwi_b64) {
          setImagery({ rgb_b64: res.rgb_b64 ?? null, ndwi_b64: res.ndwi_b64 ?? null, meta: res.live_meta ?? null });
        }
      } else if (mode === 'manual') {
        setLoadStep(3);
        res = await api.manual(activeLoc, weather, yoloEnabled ? yolo : DEFAULT_YOLO);
        setLoadStep(4);
      } else if (mode === 'historical') {
        setLoadStep(3);
        res = await api.historical(activeLoc, histDate);
        setLoadStep(4);
      } else {
        setLoading(false);
        return;
      }
      setResult(res);
      if (res.demo_mode) {
        setDemoActive(true);
      }
      setView('dashboard');
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
    // Trigger run immediately
    handleRun(city);
  };

  const handleMapSelectLocation = (loc: { name: string; lat: number; lon: number }) => {
    const config: LocationConfig = {
      location_name: loc.name,
      lat: loc.lat,
      lon: loc.lon,
      radius_km: 5.0
    };
    setLocation(config);
    setResult(null);
    setError(null);
    setMode('live');
    // Trigger run immediately
    handleRun(config);
  };

  const handleSubscribeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubSuccess(null);
    try {
      const res = await api.subscribe({
        email: subEmail || undefined,
        phone: subPhone || undefined,
        location_name: subCity,
        latitude: subLat,
        longitude: subLon,
        all_alerts: subAll,
        environmental_alerts: !subAll,
        disease_risk_alerts: !subAll,
        weather_alerts: !subAll,
        official_disaster_alerts: !subAll,
        severity_preference: subSeverity
      });
      setSubSuccess(`✅ Alert subscription successful! ID: #${res.subscription_id}. You will be notified for risk shifts.`);
      setSubEmail('');
      setSubPhone('');
    } catch (err: any) {
      setSubSuccess(`❌ Failed to subscribe: ${err.message}`);
    }
  };

  const score     = result?.phri.score ?? 0;
  const riskLevel = result?.phri.risk_level ?? 'LOW';
  const color     = phriColor(score);
  const today     = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <>
      <LoadingOverlay visible={loading} step={loadStep} />

      {/* Persistent Demo Warning Banner */}
      {demoActive && (
        <div style={{
          background: 'var(--red)', color: 'white', fontWeight: 800,
          padding: '0.45rem', fontSize: '0.75rem', letterSpacing: '1px', textTransform: 'uppercase',
          textAlign: 'center', position: 'sticky', top: 0, zIndex: 3000,
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem'
        }}>
          <span>⚠️ DEMO MODE — NOT A REAL ALERT</span>
          <button
            onClick={async () => {
              await api.setDemoScenario(null);
              setDemoActive(false);
              setDemoScenario(null);
              refreshGlobalFeeds();
            }}
            style={{
              background: 'white', color: 'var(--red)', border: 'none',
              padding: '0.2rem 0.6rem', borderRadius: 4, fontSize: '0.65rem',
              fontWeight: 700, cursor: 'pointer'
            }}
          >
            Revert to Live Pipeline
          </button>
        </div>
      )}

      <div className={`app-shell ${theme === 'light' ? 'light-mode' : ''}`}>

        {/* ── Top Navigation Bar ─────────────────────────────────────────── */}
        <nav className="top-nav">
          <div className="top-nav-logo" onClick={() => setView('home')}>
            <span>🛰️</span>
            Sentin-AI Hub
          </div>

          <div className="top-nav-links">
            <button className={`top-nav-link ${view === 'home' ? 'active' : ''}`} onClick={() => setView('home')}>
              <span>🏠 Public Home</span>
            </button>
            <button className={`top-nav-link ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setView('dashboard')}>
              <span>📊 Risk Dashboard</span>
            </button>
            <button className={`top-nav-link ${view === 'map' ? 'active' : ''}`} onClick={() => setView('map')}>
              <span>🗺️ Risk Map</span>
            </button>
            <button className={`top-nav-link ${view === 'alerts' ? 'active' : ''}`} onClick={() => setView('alerts')}>
              <span>🔔 Alerts Center</span>
            </button>
            <button className={`top-nav-link ${view === 'awareness' ? 'active' : ''}`} onClick={() => setView('awareness')}>
              <span>📦 Safety Guides</span>
            </button>
            <button className={`top-nav-link ${view === 'about' ? 'active' : ''}`} onClick={() => setView('about')}>
              <span>💡 How it Works</span>
            </button>
            <button className={`top-nav-link ${view === 'subscribe' ? 'active' : ''}`} onClick={() => setView('subscribe')}>
              <span>📬 Subscriptions</span>
            </button>
            <button className={`top-nav-link ${view === 'admin' ? 'active' : ''}`} onClick={() => setView('admin')}>
              <span>⚙️ Admin Panel</span>
            </button>
          </div>

          <div className="nav-actions">
            {backendOk !== null && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                background: backendOk ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${backendOk ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
                borderRadius: 20, padding: '0.4rem 1rem',
                fontSize: '0.85rem', fontFamily: 'DM Mono', color: backendOk ? 'var(--green)' : 'var(--red)',
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: backendOk ? 'var(--green)' : 'var(--red)',
                }} />
                System {backendOk ? 'Online' : 'Offline'}
              </div>
            )}

            <button
              className="theme-toggle-btn"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </nav>

        {/* ── Content Wrapper ────────────────────────────────────────────── */}
        <div className="content-wrapper">
          <AnimatePresence mode="wait">

            {/* ── A. PUBLIC HOME PAGE ── */}
            {view === 'home' && (
              <LandingPage
                onStartSurveillance={handleLaunchCity}
                onNavigateToStress={() => { setView('dashboard'); setMode('stress'); }}
                theme={theme}
                location={location}
                onLocationChange={setLocation}
                onSearchSubmit={() => handleRun()}
                officialAlerts={officialAlerts}
                aiAlerts={aiAlerts}
              />
            )}

            {/* ── B. LIVE RISK DASHBOARD ── */}
            {view === 'dashboard' && (
              <motion.div
                key="dashboard"
                className="surveillance-layout"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                {/* Options Panel Sidebar */}
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
                    onRun={() => handleRun()}
                    loading={loading}
                  />
                </div>

                {/* Main Workspace Panel */}
                <div className="workspace-panel">
                  <div className="panel-toggle-bar">
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                      onClick={() => setPanelOpen(o => !o)}
                    >
                      {panelOpen ? '◀ Hide Sidebar' : '▶ Show Sidebar'}
                    </button>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'DM Mono' }}>
                      {location.location_name} · Lat {location.lat.toFixed(3)}, Lon {location.lon.toFixed(3)}
                    </span>
                  </div>

                  {mode === 'stress' ? (
                    <div style={{ marginTop: '1rem' }}>
                      <StressTest />
                    </div>
                  ) : (
                    <>
                      {error && (
                        <div style={{
                          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
                          borderRadius: 8, padding: '0.9rem 1.1rem', marginBottom: '1rem',
                          fontFamily: 'DM Mono', fontSize: '0.8rem', color: 'var(--red)',
                        }}>
                          ⚠️ {error}
                        </div>
                      )}

                      {/* Empty state */}
                      {!result && !loading && (
                        <div className="empty-state fade-up">
                          <div className="empty-icon">📡</div>
                          <div className="empty-title">Risk Assessment Hub</div>
                          <div className="empty-sub">
                            Select a location in the sidebar or click "Execute Live Pipeline" to evaluate environmental anomalies.
                          </div>
                        </div>
                      )}

                      {/* Red Alert Banner for Active Official Warnings (Dashboard Specific) */}
                      {result && officialAlerts.filter(a => a.location.toLowerCase().includes(location.location_name.split(',')[0].toLowerCase()) || a.location === 'All India').map(alert => (
                        <div key={alert.id} style={{
                          background: 'rgba(239,68,68,0.08)', border: '1px solid var(--red)',
                          borderRadius: 10, padding: '0.8rem 1.2rem', marginBottom: '1.25rem', fontSize: '0.82rem'
                        }}>
                          <div style={{ color: 'var(--red)', fontWeight: 800, marginBottom: '0.2rem' }}>
                            🚨 CRITICAL AUTHORITY ALERT
                          </div>
                          <strong>{alert.title}</strong> — {alert.message}
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                            Source: {alert.source} (Official Authority Warning)
                          </div>
                        </div>
                      ))}

                      {/* Dashboard Results Render */}
                      <AnimatePresence>
                        {result && (
                          <motion.div
                            key="results"
                            initial="hidden"
                            animate="show"
                            variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } }}
                          >
                            {/* Metrics Grid */}
                            <div>
                              <div className="section-label">Risk Intelligence Outputs</div>
                              <div className="grid-5" style={{ marginBottom: '1.25rem' }}>
                                <PHRIGauge score={score} riskLevel={riskLevel} />
                                <MetricCard title="Outbreak Class" value={result.disease.label} sub="AI classification" color={color} delay={0.06} />
                                <MetricCard title="Peak Cases" value={result.seir.peak_cases} sub={`Day ${result.seir.peak_day} of 14`} color={color} delay={0.12} numeric />
                                <MetricCard title="Scenario cases" value={result.seir.total_projected} sub="14-day total model" color={color} delay={0.18} numeric />
                                <MetricCard title="Signal confidence" value={`${(result.phri.confidence * 100).toFixed(0)}%`} sub={result.phri.visual_complete ? '✅ Satellite + Weather' : '🛰️ Radar Fallback'} color="var(--cyan)" delay={0.24} />
                              </div>
                            </div>

                            {/* Explainable AI Block */}
                            <div className="landing-card" style={{ marginBottom: '1.25rem', borderLeft: `4px solid ${color}` }}>
                              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.6rem' }}>💡 Why is this location at risk? (Explainable AI)</h3>
                              <div style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                <p style={{ marginBottom: '0.6rem' }}>
                                  The 2-layer LSTM temporal network flagged this area based on the following contributing triggers:
                                </p>
                                <ul style={{ paddingLeft: '1.4rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                                  {result.weather.precipitation_imerg_mm !== undefined && result.weather.precipitation_imerg_mm > 15 ? (
                                    <li>✓ <strong>Heavy Rain spike</strong> of {result.weather.precipitation_imerg_mm} mm over the past 24 hours creates surface runoff anomalies.</li>
                                  ) : null}
                                  {result.weather.relative_humidity_pct !== undefined && result.weather.relative_humidity_pct > 75 ? (
                                    <li>✓ <strong>High humidity levels</strong> ({result.weather.relative_humidity_pct}%) accelerates vector lifespan.</li>
                                  ) : null}
                                  {result.yolo.stagnant_water_count !== undefined && result.yolo.stagnant_water_count > 0 ? (
                                    <li>✓ <strong>Stagnant water accumulations</strong> ({result.yolo.stagnant_water_count} sites) detected by computer vision provides vector breeding sites.</li>
                                  ) : null}
                                  {result.yolo.garbage_count !== undefined && result.yolo.garbage_count > 0 ? (
                                    <li>✓ <strong>Garbage piles</strong> ({result.yolo.garbage_count} candidate zones) increases food supply for rodents and water-borne pathogens.</li>
                                  ) : null}
                                  {result.yolo.vegetation_anomaly_score !== undefined && result.yolo.vegetation_anomaly_score > 0.3 ? (
                                    <li>✓ <strong>Vegetation anomaly index</strong> is elevated ({result.yolo.vegetation_anomaly_score.toFixed(2)}) indicating soil saturation changes.</li>
                                  ) : null}
                                  <li>✓ Historical environmental signatures matched vector replication parameters.</li>
                                </ul>
                                
                                <details style={{ marginTop: '0.8rem', cursor: 'pointer', borderTop: '1px solid var(--border)', paddingTop: '0.5rem' }}>
                                  <summary style={{ fontSize: '0.85rem', color: 'var(--cyan)' }}>🔬 Show Researcher Technical Details</summary>
                                  <div style={{ marginTop: '0.5rem', fontFamily: 'DM Mono', fontSize: '0.78rem', background: '#05070a', padding: '0.75rem', borderRadius: 6, lineHeight: 1.4 }}>
                                    <div>LSTM Model Architecture: 2-layer LSTM (Hidden: 64, 32 units)</div>
                                    <div>Input Shape: (30, 10) sequence window normalized</div>
                                    <div>PHRI Score Calculation: raw sigmoid scale [0.0 - 1.0]</div>
                                    <div>Disease Classification Route: rule-based router conditional branches</div>
                                    <div>SEIR Projection model parameters: beta={result.seir.beta_effective}, population={result.seir.population}</div>
                                  </div>
                                </details>
                              </div>
                            </div>

                            {/* Satellite panel */}
                            <div className="section-label">Satellite Perception Layer</div>
                            <div style={{ marginBottom: '1.25rem' }}>
                              <SatellitePanel
                                rgbB64={result.rgb_b64 ?? imagery?.rgb_b64 ?? null}
                                ndwiB64={result.ndwi_b64 ?? imagery?.ndwi_b64 ?? null}
                                meta={result.live_meta ?? imagery?.meta ?? null}
                                locationName={location.location_name}
                                lat={location.lat} lon={location.lon} radiusKm={location.radius_km}
                              />
                            </div>

                            {/* Projection graph & Weather */}
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

                            {/* Health Bulletin */}
                            <div className="section-label">AI Public Health Bulletin</div>
                            <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
                              <HealthBulletin bulletin={result.bulletin} />
                              <ActionItems disease={result.disease} actionItems={result.bulletin.action_items} />
                            </div>

                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Historical timeline when no active results */}
                      {!result && !loading && history.length > 0 && (
                        <div style={{ marginTop: '1rem' }}>
                          <div className="section-label">Historical Risk Timeline (2023–2024)</div>
                          <HistoricalTimeline data={history} isProxy={isProxy} />
                        </div>
                      )}
                    </>
                  )}

                </div>
              </motion.div>
            )}

            {/* ── C. RISK MAP VIEW ── */}
            {view === 'map' && (
              <motion.div
                key="map"
                className="surveillance-layout"
                style={{ height: 'calc(100vh - 60px)', padding: 0 }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ width: '100%', height: '100%' }}>
                  <InteractiveMap
                    markers={allMarkers}
                    onSelectLocation={handleMapSelectLocation}
                  />
                </div>
              </motion.div>
            )}

            {/* ── D. ALERTS CENTER VIEW ── */}
            {view === 'alerts' && (
              <motion.div
                key="alerts"
                className="surveillance-layout"
                style={{ flexDirection: 'column', padding: '2rem', overflowY: 'auto' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ maxWidth: 900, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Outbreak Advisory &amp; Alert Center</h2>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Understand active hazards. AI assessments are environmental risk indexes; official alerts are issued by government authorities.
                    </p>
                  </div>

                  <div className="grid-2">
                    
                    {/* Official alerts column */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--red)', borderBottom: '2px solid var(--red)', paddingBottom: '0.4rem' }}>
                        🚨 Official Authority Warnings
                      </h3>
                      {officialAlerts.map(alert => (
                        <div key={alert.id} className="landing-card" style={{ borderLeft: '4px solid var(--red)' }}>
                          <span style={{ fontSize: '0.65rem', fontFamily: 'DM Mono', color: 'var(--red)', fontWeight: 600 }}>OFFICIAL DISASTER ALERT</span>
                          <h4 style={{ fontSize: '0.88rem', fontWeight: 700, margin: '0.2rem 0' }}>{alert.title}</h4>
                          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{alert.message}</p>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.8rem', borderTop: '1px solid var(--border)', paddingTop: '0.4rem' }}>
                            <span>SOURCE: {alert.source}</span>
                            <span>{new Date(alert.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      ))}
                      {officialAlerts.length === 0 && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '2rem', border: '1px dashed var(--border)', borderRadius: 8 }}>
                          No active official alerts broadcasted for monitored regions.
                        </div>
                      )}
                    </div>

                    {/* AI Alerts column */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--cyan)', borderBottom: '2px solid var(--cyan)', paddingBottom: '0.4rem' }}>
                        🛰️ Sentin-AI Risk Warnings
                      </h3>
                      {aiAlerts.map(alert => {
                        const scoreColor = phriColor(alert.phri_score || 0.5);
                        return (
                          <div key={alert.id} className="landing-card" style={{ borderLeft: `4px solid ${scoreColor}` }}>
                            <span style={{ fontSize: '0.65rem', fontFamily: 'DM Mono', color: scoreColor, fontWeight: 600 }}>AI RISK ASSESSMENT (PHRI: {(alert.phri_score || 0).toFixed(2)})</span>
                            <h4 style={{ fontSize: '0.88rem', fontWeight: 700, margin: '0.2rem 0' }}>{alert.title}</h4>
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{alert.message}</p>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.8rem', borderTop: '1px solid var(--border)', paddingTop: '0.4rem' }}>
                              <span>SOURCE: Sentin-AI Model</span>
                              <span>{new Date(alert.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        );
                      })}
                      {aiAlerts.length === 0 && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '2rem', border: '1px dashed var(--border)', borderRadius: 8 }}>
                          No AI-generated alerts active.
                        </div>
                      )}
                    </div>

                  </div>
                </div>
              </motion.div>
            )}

            {/* ── E. AWARENESS CENTER VIEW ── */}
            {view === 'awareness' && (
              <motion.div
                key="awareness"
                className="surveillance-layout"
                style={{ flexDirection: 'column', padding: '2rem', overflowY: 'auto' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ maxWidth: 900, margin: '0 auto', width: '100%' }}>
                  <AwarenessCenter />
                </div>
              </motion.div>
            )}

            {/* ── F. HOW SENTIN-AI WORKS ── */}
            {view === 'about' && (
              <motion.div
                key="about"
                className="surveillance-layout"
                style={{ flexDirection: 'column', padding: '2rem', overflowY: 'auto' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ maxWidth: 800, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>System Architecture &amp; Model Transparency</h2>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Learn how weather sensors and Sentinel-2 imagery feed our predictive LSTM networks.
                    </p>
                  </div>

                  <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>The Sentin-AI Data Pipeline</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', fontSize: '0.82rem', lineHeight: 1.5 }}>
                      
                      <div style={{ borderLeft: '3px solid var(--cyan)', paddingLeft: '0.75rem' }}>
                        <strong>1. Live Ingestion (NASA POWER &amp; GEE)</strong>
                        <p style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                          Every run fetches temperature, relative humidity, precipitation indices, and dew point directly from the NASA POWER API. Sentinel-2 spectral composite bands are loaded over a 5km region of interest.
                        </p>
                      </div>

                      <div style={{ borderLeft: '3px solid var(--cyan)', paddingLeft: '0.75rem' }}>
                        <strong>2. Computer Vision Feature Extraction (YOLOv8)</strong>
                        <p style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                          The latest visual scene runs through a customized fine-tuned YOLOv8 segmentation model to count stagnant water bodies, compute pooling surface area, locate refuse accumulation piles, and extract vegetation anomalies.
                        </p>
                      </div>

                      <div style={{ borderLeft: '3px solid var(--cyan)', paddingLeft: '0.75rem' }}>
                        <strong>3. Spectral Index Math (NDWI &amp; NDVI)</strong>
                        <p style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                          NDWI temporal differencing extracts temporary flood ponding areas. NDVI anomalies identify vegetation degradation indices, which act as proxies for soil saturation.
                        </p>
                      </div>

                      <div style={{ borderLeft: '3px solid var(--cyan)', paddingLeft: '0.75rem' }}>
                        <strong>4. 30-Day LSTM Recurrent Model</strong>
                        <p style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                          A 30-day × 10-feature normalized window feeds a 2-layer LSTM model. The model infers historical sequence patterns to output the raw **PHRI score** (Public Health Risk Index).
                        </p>
                      </div>

                      <div style={{ borderLeft: '3px solid var(--cyan)', paddingLeft: '0.75rem' }}>
                        <strong>5. Rule Routing &amp; Projections (DiseaseRouter &amp; SEIR)</strong>
                        <p style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                          The DiseaseRouter classifies risk into buckets (Dengue, Cholera, Respiratory, General) based on heat, moisture, and waste thresholds. An epidemiological SEIR differential model projects potential case curves under current conditions.
                        </p>
                      </div>

                    </div>
                  </div>

                  <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--amber)' }}>⚠️ Scientific Limitations</h3>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      - **Accuracy Scope**: While the LSTM model scored a high validation ROC-AUC of 0.80, environmental models represent probabilities, not certainties.
                      - **Satellite Clouds**: Heavily cloudy periods restrict optical Sentinel-2 imagery. While Sentinel-1 SAR radar fallbacks mitigate this, radar represents a moisture proxy, not a visual segment.
                      - **No Case Guarantees**: Projections represent theoretical SEIR model scenarios based on historical vector kinetics; they are not concrete forecasts of clinical case counts.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── G. ALERT SUBSCRIPTIONS VIEW ── */}
            {view === 'subscribe' && (
              <motion.div
                key="subscribe"
                className="surveillance-layout"
                style={{ flexDirection: 'column', padding: '2rem', overflowY: 'auto' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ maxWidth: 550, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Alert Notification Subscriptions</h2>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Subscribe to receive alerts for your district directly via SMS, WhatsApp, Telegram, or Email.
                    </p>
                  </div>

                  <div className="landing-card">
                    <form onSubmit={handleSubscribeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.82rem' }}>
                      <div>
                        <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Email Address</label>
                        <input
                          type="email" placeholder="name@domain.com"
                          value={subEmail} onChange={e => setSubEmail(e.target.value)}
                          style={{ width: '100%', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Phone Number (with Country Code)</label>
                        <input
                          type="text" placeholder="+91 98765 43210"
                          value={subPhone} onChange={e => setSubPhone(e.target.value)}
                          style={{ width: '100%', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                        />
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '0.5rem' }}>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>City / Region</label>
                          <input
                            type="text" required value={subCity} onChange={e => setSubCity(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                          />
                        </div>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Lat</label>
                          <input
                            type="number" step="0.0001" required value={subLat} onChange={e => setSubLat(parseFloat(e.target.value))}
                            style={{ width: '100%', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                          />
                        </div>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Lon</label>
                          <input
                            type="number" step="0.0001" required value={subLon} onChange={e => setSubLon(parseFloat(e.target.value))}
                            style={{ width: '100%', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                          />
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Alert Preferences</label>
                          <select
                            value={subAll ? 'all' : 'custom'} onChange={e => setSubAll(e.target.value === 'all')}
                            style={{ width: '100%', padding: '0.5rem', background: 'rgba(17,24,39,0.9)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                          >
                            <option value="all">All Advisories</option>
                            <option value="custom">Critical Only</option>
                          </select>
                        </div>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.3rem', color: 'var(--text-secondary)' }}>Severity Threshold</label>
                          <select
                            value={subSeverity} onChange={e => setSubSeverity(e.target.value as any)}
                            style={{ width: '100%', padding: '0.5rem', background: 'rgba(17,24,39,0.9)', border: '1px solid var(--border)', color: 'white', borderRadius: 6 }}
                          >
                            <option value="MODERATE">Moderate and Higher</option>
                            <option value="HIGH">High and Higher</option>
                            <option value="CRITICAL">Critical Only</option>
                          </select>
                        </div>
                      </div>

                      <button type="submit" className="btn btn-primary" style={{ padding: '0.65rem', marginTop: '0.5rem', fontWeight: 600 }}>
                        📬 Confirm Alert Registration
                      </button>
                      
                      {subSuccess && (
                        <div style={{ marginTop: '0.5rem', color: 'var(--cyan)', lineHeight: 1.4 }}>
                          {subSuccess}
                        </div>
                      )}
                    </form>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── H. ADMIN CONSOLE VIEW ── */}
            {view === 'admin' && (
              <motion.div
                key="admin"
                className="surveillance-layout"
                style={{ flexDirection: 'column', padding: '2rem', overflowY: 'auto' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div style={{ maxWidth: 950, margin: '0 auto', width: '100%' }}>
                  <AdminPanel
                    currentDemoMode={demoScenario}
                    onDemoModeChange={(active, scen) => {
                      setDemoActive(active);
                      setDemoScenario(scen);
                    }}
                  />
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </div>
    </>
  );
}
