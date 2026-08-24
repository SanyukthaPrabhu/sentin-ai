import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import type { LocationConfig, ManualWeather, ManualYolo } from '../api';
import CustomDropdown from './CustomDropdown';

const CITIES: LocationConfig[] = [
  { lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka' },
  { lat: 19.07, lon: 72.87, radius_km: 5, location_name: 'Mumbai, Maharashtra' },
  { lat: 28.61, lon: 77.20, radius_km: 5, location_name: 'New Delhi, NCR' },
  { lat: 13.08, lon: 80.27, radius_km: 5, location_name: 'Chennai, Tamil Nadu' },
  { lat: 17.38, lon: 78.48, radius_km: 5, location_name: 'Hyderabad, Telangana' },
  { lat: 22.57, lon: 88.36, radius_km: 5, location_name: 'Kolkata, West Bengal' },
  { lat: 34.15, lon:  77.57, radius_km: 5, location_name: 'Leh, Ladakh' },
];

const MODES = [
  { id: 'live',       icon: '⚡', label: 'Live Pipeline' },
  { id: 'manual',     icon: '🎛️', label: 'Manual Input' },
  { id: 'historical', icon: '📅', label: 'Historical' },
  { id: 'stress',     icon: '🧪', label: 'Stress Test' },
];

const WEATHER_SLIDERS: { key: keyof ManualWeather; label: string; min: number; max: number; step: number; unit: string }[] = [
  { key: 'temperature_2m_c',            label: 'Temperature',     min: 5,   max: 45,  step: 0.5, unit: '°C' },
  { key: 'relative_humidity_pct',       label: 'Humidity',        min: 0,   max: 100, step: 1,   unit: '%'  },
  { key: 'precipitation_imerg_mm',      label: 'Precipitation',   min: 0,   max: 100, step: 0.5, unit: 'mm' },
  { key: 'dew_frost_point_c',           label: 'Dew Point',       min: -10, max: 35,  step: 0.5, unit: '°C' },
  { key: 'wind_speed_10m_ms',           label: 'Wind Speed',      min: 0,   max: 20,  step: 0.5, unit: 'm/s' },
  { key: 'all_sky_insolation_clearness',label: 'Insolation',      min: 0,   max: 1,   step: 0.01, unit: '' },
];

const YOLO_SLIDERS: { key: keyof ManualYolo; label: string; min: number; max: number; step: number }[] = [
  { key: 'stagnant_water_count',    label: 'Water Count',    min: 0, max: 20,    step: 1 },
  { key: 'stagnant_water_area_px',  label: 'Water Area px',  min: 0, max: 50000, step: 100 },
  { key: 'garbage_count',           label: 'Garbage Count',  min: 0, max: 20,    step: 1 },
  { key: 'vegetation_anomaly_score',label: 'Veg Anomaly',    min: 0, max: 1,     step: 0.01 },
];

interface Props {
  mode:        string;
  location:    LocationConfig;
  weather:     ManualWeather;
  yolo:        ManualYolo;
  histDate:    string;
  yoloEnabled: boolean;
  onModeChange:    (m: string) => void;
  onLocationChange:(l: LocationConfig) => void;
  onWeatherChange: (w: ManualWeather) => void;
  onYoloChange:    (y: ManualYolo) => void;
  onHistDateChange:(d: string) => void;
  onYoloToggle:    (v: boolean) => void;
  onRun:           () => void;
  loading:         boolean;
}

function RangeSlider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit: string;
  onChange: (v: number) => void;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ marginBottom: '0.85rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
        <span className="sidebar-label" style={{ marginBottom: 0 }}>{label}</span>
        <span style={{ fontFamily: 'DM Mono', fontSize: '0.88rem', fontWeight: 'bold', color: 'var(--cyan)' }}>
          {value}{unit}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        style={{ '--pct': `${pct}%` } as React.CSSProperties}
        onChange={e => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}

export default function Sidebar({
  mode, location, weather, yolo, histDate, yoloEnabled,
  onModeChange, onLocationChange, onWeatherChange, onYoloChange,
  onHistDateChange, onYoloToggle, onRun, loading
}: Props) {
  const [cityIdx, setCityIdx] = useState(0);
  const [customLat, setCustomLat] = useState(String(location.lat));
  const [customLon, setCustomLon] = useState(String(location.lon));
  const [customName, setCustomName] = useState(location.location_name);

  useEffect(() => {
    setCustomLat(String(location.lat));
    setCustomLon(String(location.lon));
    setCustomName(location.location_name);

    const idx = CITIES.findIndex(
      c => Math.abs(c.lat - location.lat) < 0.001 && Math.abs(c.lon - location.lon) < 0.001
    );
    setCityIdx(idx);
  }, [location.lat, location.lon, location.location_name]);

  const handleCityChange = (idx: number) => {
    if (idx === -1) {
      setCityIdx(-1);
      return;
    }
    setCityIdx(idx);
    onLocationChange(CITIES[idx]);
    setCustomLat(String(CITIES[idx].lat));
    setCustomLon(String(CITIES[idx].lon));
    setCustomName(CITIES[idx].location_name);
  };

  const applyCustom = () => {
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);
    if (!isNaN(lat) && !isNaN(lon)) {
      onLocationChange({ ...location, lat, lon, location_name: customName });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Location */}
      <div style={{ marginBottom: '1.25rem' }}>
        <CustomDropdown
          label="📍 Surveillance Location"
          options={[
            ...CITIES.map((c, i) => ({ value: String(i), label: c.location_name })),
            { value: '-1', label: 'Custom…' }
          ]}
          value={String(cityIdx)}
          onChange={val => handleCityChange(parseInt(val))}
        />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', marginBottom: '0.4rem' }}>
          <div>
            <span className="sidebar-label">Lat</span>
            <input className="sidebar-input" type="number" step="0.01" value={customLat}
              onChange={e => setCustomLat(e.target.value)} onBlur={applyCustom} />
          </div>
          <div>
            <span className="sidebar-label">Lon</span>
            <input className="sidebar-input" type="number" step="0.01" value={customLon}
              onChange={e => setCustomLon(e.target.value)} onBlur={applyCustom} />
          </div>
        </div>

        <div style={{ marginBottom: '0.6rem' }}>
          <span className="sidebar-label">Location Name</span>
          <input className="sidebar-input" type="text" value={customName}
            onChange={e => setCustomName(e.target.value)} onBlur={applyCustom} />
        </div>

        <RangeSlider label="Radius (km)" value={location.radius_km}
          min={1} max={25} step={1} unit=" km"
          onChange={v => onLocationChange({ ...location, radius_km: v })} />
      </div>

      <div className="divider" />

      {/* Mode tabs */}
      <div style={{ marginBottom: '1.25rem' }}>
        <span className="sidebar-label">⚙️ Analysis Mode</span>
        <div className="mode-tabs" style={{ display: 'flex', gap: '4px', background: 'var(--bg-void)', padding: '4px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-glow)' }}>
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-tab ${mode === m.id ? 'active' : ''}`}
              onClick={() => onModeChange(m.id)}
              style={{
                position: 'relative',
                flex: 1,
                padding: '0.65rem 0.75rem',
                fontSize: '0.88rem',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                outline: 'none',
                borderRadius: 'calc(var(--radius-sm) - 2px)',
                transition: 'color 0.15s'
              }}
            >
              {mode === m.id && (
                <motion.div
                  layoutId="activeModeIndicator"
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-glow)',
                    borderRadius: 'calc(var(--radius-sm) - 2px)',
                    zIndex: 0,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                  }}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              <span style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}>
                <span>{m.icon}</span>
                <span>{m.label}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Historical date picker */}
      {mode === 'historical' && (
        <div style={{ marginBottom: '1.25rem' }}>
          <div className="divider" />
          <span className="sidebar-label">📅 Select Date</span>
          <input
            type="date"
            className="sidebar-input"
            value={histDate}
            min="2023-01-31"
            max="2024-12-31"
            onChange={e => onHistDateChange(e.target.value)}
          />
        </div>
      )}

      {/* Manual weather sliders */}
      {mode === 'manual' && (
        <>
          <div className="divider" />
          <span className="sidebar-label">🌡️ Weather Parameters</span>
          {WEATHER_SLIDERS.map(s => (
            <RangeSlider key={s.key} label={s.label} unit={s.unit}
              value={(weather as any)[s.key]} min={s.min} max={s.max} step={s.step}
              onChange={v => onWeatherChange({ ...weather, [s.key]: v })} />
          ))}

          <div className="divider" />

          {/* YOLO toggle */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: yoloEnabled ? '0.75rem' : 0 }}>
            <span className="sidebar-label" style={{ marginBottom: 0 }}>🛰️ YOLO Features</span>
            <button
              onClick={() => onYoloToggle(!yoloEnabled)}
              style={{
                width: 36, height: 20, borderRadius: 10, border: 'none',
                background: yoloEnabled ? 'var(--cyan)' : 'rgba(255,255,255,0.1)',
                position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
              }}
            >
              <span style={{
                position: 'absolute', top: 2,
                left: yoloEnabled ? 18 : 2,
                width: 16, height: 16, borderRadius: '50%',
                background: '#fff', transition: 'left 0.2s',
              }} />
            </button>
          </div>

          {yoloEnabled && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              transition={{ duration: 0.3 }}
            >
              {YOLO_SLIDERS.map(s => (
                <RangeSlider key={s.key} label={s.label} unit=""
                  value={(yolo as any)[s.key]} min={s.min} max={s.max} step={s.step}
                  onChange={v => onYoloChange({ ...yolo, [s.key]: v })} />
              ))}
            </motion.div>
          )}
        </>
      )}

      {/* Run button (not shown for stress test) */}
      {mode !== 'stress' && (
        <>
          <div style={{ flex: 1 }} />
          <div className="divider" style={{ marginTop: 'auto' }} />
          <button
            className="btn btn-primary btn-full"
            onClick={onRun}
            disabled={loading}
          >
            {loading ? '⏳ Running…' : mode === 'live' ? '⚡ Execute Live Pipeline' : '▶ Run Analysis'}
          </button>
          <div style={{ fontFamily: 'DM Mono', fontSize: '0.65rem', color: 'var(--text-muted)',
            textAlign: 'center', marginTop: '0.5rem' }}>
            {location.location_name}
          </div>
        </>
      )}
    </div>
  );
}
