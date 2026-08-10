import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip
} from 'recharts';
import { motion } from 'framer-motion';
import type { ManualWeather } from '../api';

interface Props {
  weather: Partial<ManualWeather>;
}

const LABELS: Record<string, string> = {
  temperature_2m_c:             'Temp °C',
  relative_humidity_pct:        'Humidity %',
  precipitation_imerg_mm:       'Rain mm',
  dew_frost_point_c:            'Dew Point',
  wind_speed_10m_ms:            'Wind m/s',
  all_sky_insolation_clearness: 'Insolation',
};

const RANGES: Record<string, [number, number]> = {
  temperature_2m_c:             [10, 45],
  relative_humidity_pct:        [0, 100],
  precipitation_imerg_mm:       [0, 80],
  dew_frost_point_c:            [-5, 30],
  wind_speed_10m_ms:            [0, 15],
  all_sky_insolation_clearness: [0, 1],
};

function normalize(key: string, v: number): number {
  const [lo, hi] = RANGES[key] || [0, 100];
  return Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-glow)',
      borderRadius: 8, padding: '0.5rem 0.75rem', fontFamily: 'DM Mono', fontSize: '0.78rem' }}>
      <div style={{ color: 'var(--cyan)' }}>{d.label}</div>
      <div style={{ color: 'var(--text-primary)' }}>Raw: {d.raw}</div>
    </div>
  );
};

export default function WeatherRadar({ weather }: Props) {
  const data = Object.keys(LABELS).map(key => ({
    label: LABELS[key],
    value: normalize(key, (weather as any)[key] ?? 0),
    raw:   (weather as any)[key] ?? 0,
  }));

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="section-label" style={{ borderBottom: 'none', marginBottom: '0.5rem' }}>
        Weather Environment
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} margin={{ top: 10, right: 25, bottom: 10, left: 25 }}>
          <PolarGrid stroke="var(--border-glow)" />
          <PolarAngleAxis dataKey="label"
            tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'DM Mono' }} />
          <Tooltip content={<CustomTooltip />} animationDuration={200} />
          <Radar dataKey="value" stroke="var(--cyan)" strokeWidth={1.5}
            fill="rgba(var(--cyan-rgb), 0.08)"
            isAnimationActive animationDuration={900} animationEasing="ease-out" />
        </RadarChart>
      </ResponsiveContainer>

      {/* Mini weather stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', marginTop: '0.5rem' }}>
        {Object.keys(LABELS).map(key => (
          <div key={key} style={{ fontFamily: 'DM Mono', fontSize: '0.72rem',
            display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0',
            borderBottom: '1px solid var(--border-glow)' }}>
            <span style={{ color: 'var(--text-muted)' }}>{LABELS[key]}</span>
            <span style={{ color: 'var(--cyan)' }}>{((weather as any)[key] ?? '—')}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
