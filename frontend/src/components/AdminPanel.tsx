import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { AdminSystemData, SystemLog } from '../api';

interface Props {
  onDemoModeChange: (active: boolean, scenario: string | null) => void;
  currentDemoMode: string | null;
}

export default function AdminPanel({ onDemoModeChange, currentDemoMode }: Props) {
  const [systemData, setSystemData] = useState<AdminSystemData | null>(null);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New location form
  const [newLocName, setNewLocName] = useState('');
  const [newLocLat, setNewLocLat] = useState(12.98);
  const [newLocLon, setNewLocLon] = useState(77.58);
  const [newLocRad, setNewLocRad] = useState(5.0);
  const [locSubmitMsg, setLocSubmitMsg] = useState<string | null>(null);

  // Inject official alert form
  const [injTitle, setInjTitle] = useState('IMD RED ALERT: Flash Flood Warning');
  const [injMsg, setInjMsg] = useState('Severe precipitation has triggered urban flash floods. Avoid travel.');
  const [injSev, setInjSev] = useState('CRITICAL');
  const [injLoc, setInjLoc] = useState('Bengaluru, Karnataka');
  const [injLat, setInjLat] = useState(12.98);
  const [injLon, setInjLon] = useState(77.58);
  const [injSource, setInjSource] = useState('India Meteorological Department (IMD)');
  const [injSubmitMsg, setInjSubmitMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAdminSystem();
      setSystemData(data);
      const systemLogs = await api.getAdminLogs(30);
      setLogs(systemLogs);
    } catch (err: any) {
      setError(err.message || 'Failed to load admin telemetry data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleDemoToggle = async (scenario: string | null) => {
    try {
      const res = await api.setDemoScenario(scenario);
      if (res.status === 'enabled') {
        onDemoModeChange(true, scenario);
      } else {
        onDemoModeChange(false, null);
      }
      loadData();
    } catch (err: any) {
      alert(`Failed to set demo scenario: ${err.message}`);
    }
  };

  const handleAddLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocSubmitMsg(null);
    try {
      const res = await api.addMonitoredLocation({
        name: newLocName,
        latitude: newLocLat,
        longitude: newLocLon,
        radius_km: newLocRad
      });
      setLocSubmitMsg(`✅ ${res.message}`);
      setNewLocName('');
      loadData();
    } catch (err: any) {
      setLocSubmitMsg(`❌ Error: ${err.message}`);
    }
  };

  const handleInjectAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    setInjSubmitMsg(null);
    try {
      const res = await api.injectOfficialAlert({
        title: injTitle,
        message: injMsg,
        severity: injSev,
        location: injLoc,
        latitude: injLat,
        longitude: injLon,
        source: injSource
      });
      setInjSubmitMsg(`✅ ${res.message}`);
      loadData();
    } catch (err: any) {
      setInjSubmitMsg(`❌ Error: ${err.message}`);
    }
  };

  if (loading && !systemData) {
    return <div style={{ color: 'var(--text-muted)', fontFamily: 'DM Mono', fontSize: '0.8rem' }}>Loading Telemetry...</div>;
  }

  const getHealthBadgeColor = (val: string) => {
    if (val === 'healthy' || val === 'online' || val === 'configured') return 'var(--green)';
    if (val === 'degraded') return 'var(--amber)';
    return 'var(--red)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', paddingBottom: '3rem' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Admin Command Console</h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Inspect system health, review logs, inject mock warnings, and toggle simulation profiles.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadData}>🔄 Refresh Telemetry</button>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 8, padding: '0.9rem 1.1rem', color: 'var(--red)', fontSize: '0.8rem', fontFamily: 'DM Mono'
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Grid: Health & Demo scenarios */}
      <div className="grid-2">
        
        {/* System Health */}
        <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
            🛰️ Platform Health Telemetry
          </h3>
          {systemData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>FastAPI Backend Services:</span>
                <span style={{ color: 'var(--green)', fontWeight: 600 }}>ONLINE</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>SQLite DB Connection:</span>
                <span style={{ color: getHealthBadgeColor(systemData.system_health.database), fontWeight: 600 }}>
                  {systemData.system_health.database.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>LSTM Outbreak Model:</span>
                <span style={{ color: getHealthBadgeColor(systemData.system_health.model), fontWeight: 600 }}>
                  {systemData.system_health.model.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>OpenWeatherMap API:</span>
                <span style={{ color: getHealthBadgeColor(systemData.system_health.weather_api), fontWeight: 600 }}>
                  {systemData.system_health.weather_api.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Google Earth Engine connection:</span>
                <span style={{ color: getHealthBadgeColor(systemData.system_health.earth_engine), fontWeight: 600 }}>
                  {systemData.system_health.earth_engine.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Notification Engine Dispatcher:</span>
                <span style={{ color: getHealthBadgeColor(systemData.system_health.notification_service), fontWeight: 600 }}>
                  {systemData.system_health.notification_service.toUpperCase()}
                </span>
              </div>
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.8rem', display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
                <div>Monitored Sites: <strong style={{ color: 'var(--cyan)' }}>{systemData.monitored_locations_count}</strong></div>
                <div>Alert Subscriptions: <strong style={{ color: 'var(--cyan)' }}>{systemData.subscriptions_count}</strong></div>
                <div>Active Alerts: <strong style={{ color: 'var(--cyan)' }}>{systemData.active_ai_alerts + systemData.active_official_alerts}</strong></div>
              </div>
            </div>
          )}
        </div>

        {/* Demo scenarios selector */}
        <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
            🧪 Platform Simulation Scenarios
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button
                onClick={() => handleDemoToggle(null)}
                className={`btn ${!currentDemoMode ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                Disable Simulation
              </button>
              <button
                onClick={() => handleDemoToggle('scenario_1')}
                className={`btn ${currentDemoMode === 'scenario_1' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                S1: Low Risk
              </button>
              <button
                onClick={() => handleDemoToggle('scenario_2')}
                className={`btn ${currentDemoMode === 'scenario_2' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                S2: Monsoon Rainfall
              </button>
              <button
                onClick={() => handleDemoToggle('scenario_3')}
                className={`btn ${currentDemoMode === 'scenario_3' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                S3: Critical Disease Risk
              </button>
              <button
                onClick={() => handleDemoToggle('scenario_4')}
                className={`btn ${currentDemoMode === 'scenario_4' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                S4: Government Alert
              </button>
              <button
                onClick={() => handleDemoToggle('scenario_5')}
                className={`btn ${currentDemoMode === 'scenario_5' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }}
              >
                S5: Radar Fallback
              </button>
            </div>
            
            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '0.75rem', fontSize: '0.78rem', lineHeight: 1.4, color: 'var(--text-secondary)'
            }}>
              {!currentDemoMode && "🟢 Running Live Data Pipeline. The system is consuming real-time weather and satellite parameters."}
              {currentDemoMode === 'scenario_1' && "✅ Simulating Baseline Conditions: PHRI remains at 0.15 (LOW). Weather, water levels, and garbage markers are optimal."}
              {currentDemoMode === 'scenario_2' && "☔ Simulating Monsoon Surge: High rainfall (42mm) and 14 stagnant pooling sites. PHRI rises to 0.68 (HIGH Dengue/Malaria risk)."}
              {currentDemoMode === 'scenario_3' && "🦟 Simulating Extreme Threat: Massive standing water bodies (28 sites) and trash waste. PHRI hits 0.88 (CRITICAL Dengue/Leptospirosis hazard)."}
              {currentDemoMode === 'scenario_4' && "🚨 Simulating Official Emergency: Injects an active critical flood warning from NDMA SACHET, showing separation of official warnings and AI risk."}
              {currentDemoMode === 'scenario_5' && "☁️ Simulating Cloud Blockage: Simulates 100% cloud cover. Optical Sentinel-2 is unavailable; system invokes Sentinel-1 SAR radar fallback."}
            </div>
          </div>
        </div>

      </div>

      {/* Grid: Monitored Locations & Alert Injector */}
      <div className="grid-2">
        
        {/* Monitored Locations Manager */}
        <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
            📍 Manage Monitored Regions
          </h3>
          
          {/* Add Form */}
          <form onSubmit={handleAddLocation} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Location Name</label>
                <input
                  type="text" required placeholder="City, State"
                  value={newLocName} onChange={e => setNewLocName(e.target.value)}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Radius (km)</label>
                <input
                  type="number" step="0.1" required
                  value={newLocRad} onChange={e => setNewLocRad(parseFloat(e.target.value))}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Latitude</label>
                <input
                  type="number" step="0.0001" required
                  value={newLocLat} onChange={e => setNewLocLat(parseFloat(e.target.value))}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Longitude</label>
                <input
                  type="number" step="0.0001" required
                  value={newLocLon} onChange={e => setNewLocLon(parseFloat(e.target.value))}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '0.5rem' }}>
              ➕ Add Location to Surveillance
            </button>
            {locSubmitMsg && <div style={{ fontSize: '0.75rem', color: 'var(--cyan)' }}>{locSubmitMsg}</div>}
          </form>
          
          {/* Monitored List */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.5rem', maxHeight: 150, overflowY: 'auto' }}>
            <h4 style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Currently Active Targets</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.75rem' }}>
              {systemData?.monitored_locations.map(loc => (
                <div key={loc.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem', background: 'rgba(255,255,255,0.01)', borderRadius: 4 }}>
                  <span>📍 {loc.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'DM Mono' }}>{loc.latitude}, {loc.longitude} ({loc.radius_km}km)</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Mock Official Alert Injector */}
        <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
            🚨 Inject Official Government Warning
          </h3>
          <form onSubmit={handleInjectAlert} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.78rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Alert Title</label>
              <input
                type="text" required value={injTitle} onChange={e => setInjTitle(e.target.value)}
                style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Message Body</label>
              <textarea
                required rows={2} value={injMsg} onChange={e => setInjMsg(e.target.value)}
                style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4, fontFamily: 'sans-serif' }}
              />
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Severity</label>
                <select
                  value={injSev} onChange={e => setInjSev(e.target.value)}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(17,24,39,0.9)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                >
                  <option value="MODERATE">Moderate</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Authority Source</label>
                <input
                  type="text" required value={injSource} onChange={e => setInjSource(e.target.value)}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: '0.5rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Target Location Name</label>
                <input
                  type="text" required value={injLoc} onChange={e => setInjLoc(e.target.value)}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Latitude</label>
                <input
                  type="number" step="0.0001" value={injLat} onChange={e => setInjLat(parseFloat(e.target.value))}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.2rem', color: 'var(--text-muted)' }}>Longitude</label>
                <input
                  type="number" step="0.0001" value={injLon} onChange={e => setInjLon(parseFloat(e.target.value))}
                  style={{ width: '100%', padding: '0.4rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', borderRadius: 4 }}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '0.5rem', background: 'var(--red)', border: 'none' }}>
              📣 Broadcast Emergency Alert
            </button>
            {injSubmitMsg && <div style={{ fontSize: '0.75rem', color: 'var(--cyan)' }}>{injSubmitMsg}</div>}
          </form>
        </div>

      </div>

      {/* System Audit Logs */}
      <div className="landing-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>📋 System Audit &amp; Event Logs</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'DM Mono' }}>Showing last 30 entries</span>
        </h3>
        <div style={{ overflowX: 'auto', maxHeight: 300, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem', fontFamily: 'DM Mono', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '0.5rem 0.25rem' }}>Timestamp</th>
                <th style={{ padding: '0.5rem 0.25rem' }}>Level</th>
                <th style={{ padding: '0.5rem 0.25rem' }}>Stage</th>
                <th style={{ padding: '0.5rem 0.25rem' }}>Location</th>
                <th style={{ padding: '0.5rem 0.25rem' }}>Inference</th>
                <th style={{ padding: '0.5rem 0.25rem' }}>Message</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => {
                let lvlColor = 'var(--text-primary)';
                if (log.level === 'WARNING') lvlColor = 'var(--amber)';
                else if (log.level === 'ERROR') lvlColor = 'var(--red)';
                else if (log.level === 'INFO') lvlColor = 'var(--green)';

                return (
                  <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', verticalAlign: 'top' }}>
                    <td style={{ padding: '0.4rem 0.25rem', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </td>
                    <td style={{ padding: '0.4rem 0.25rem', fontWeight: 600, color: lvlColor }}>
                      {log.level}
                    </td>
                    <td style={{ padding: '0.4rem 0.25rem', color: 'var(--cyan)' }}>
                      {log.stage || '—'}
                    </td>
                    <td style={{ padding: '0.4rem 0.25rem' }}>
                      {log.location || '—'}
                    </td>
                    <td style={{ padding: '0.4rem 0.25rem', color: 'var(--text-muted)' }}>
                      {log.model_inference_time_ms ? `${log.model_inference_time_ms.toFixed(0)}ms` : '—'}
                    </td>
                    <td style={{ padding: '0.4rem 0.25rem', color: 'var(--text-secondary)' }}>
                      {log.message}
                      {log.error_details && (
                        <details style={{ marginTop: '0.2rem', cursor: 'pointer', color: 'var(--red)' }}>
                          <summary>Stack Trace</summary>
                          <pre style={{ overflowX: 'auto', padding: '0.4rem', background: '#05070a', borderRadius: 4, fontSize: '0.65rem', marginTop: '0.2rem' }}>
                            {log.error_details}
                          </pre>
                        </details>
                      )}
                    </td>
                  </tr>
                );
              })}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No audit logs available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
