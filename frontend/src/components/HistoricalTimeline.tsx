import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Brush
} from 'recharts';
import { motion } from 'framer-motion';
import type { HistoryPoint } from '../api';

interface Props { data: HistoryPoint[]; isProxy?: boolean; }

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as HistoryPoint;
  return (
    <div style={{ background: '#0f131f', border: '1px solid var(--border-glow)',
      borderRadius: 6, padding: '0.6rem 0.9rem', fontFamily: 'DM Sans', fontSize: '0.8rem' }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{d.date}</div>
      <div style={{ color: 'var(--cyan)' }}>PHRI: {d.phri.toFixed(3)}</div>
      <div style={{ color: 'var(--text-primary)' }}>Temp: {d.temp}°C</div>
      <div style={{ color: 'var(--text-primary)' }}>Rain: {d.rain} mm</div>
      <div style={{ color: 'var(--text-primary)' }}>Humidity: {d.humid}%</div>
    </div>
  );
};

export default function HistoricalTimeline({ data, isProxy = true }: Props) {
  if (!data.length) return (
    <div className="empty-state">
      <div className="empty-icon">📊</div>
      <div className="empty-title">No Historical Data</div>
      <div className="empty-sub">Run `python src/nasa_power_parser.py` first.</div>
    </div>
  );

  // Sample down to max 180 points for performance
  const sampled = data.length > 180
    ? data.filter((_, i) => i % Math.ceil(data.length / 180) === 0)
    : data;

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <div className="section-label" style={{ borderBottom: 'none', marginBottom: 2 }}>
            Historical Risk Timeline
          </div>
          <div style={{ fontFamily: 'Syne', fontSize: '0.9rem', fontWeight: 600, color: '#e8edf5' }}>
            {isProxy ? '2023–2024 PHRI Proxy (Weather-based)' : '2023–2024 LSTM Model PHRI'}
          </div>
        </div>
        <div style={{ fontFamily: 'DM Mono', fontSize: '0.72rem', color: '#6b7a99' }}>
          {data.length} days
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={sampled} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <defs>
            <linearGradient id="risk-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(255,76,76,0.15)" />
              <stop offset="100%" stopColor="transparent" />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-glow)" />
          <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} interval={Math.ceil(sampled.length / 8)} />
          <YAxis domain={[0, 1]} tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} tickFormatter={v => v.toFixed(1)} />
          <Tooltip content={<CustomTooltip />} animationDuration={200} />
          {/* Alert threshold band */}
          <ReferenceLine y={0.70} stroke="rgba(239,68,68,0.3)" strokeDasharray="5 3"
            label={{ value: 'Alert 0.70', fill: 'var(--red)', fontSize: 9, fontFamily: 'DM Mono', position: 'right' }} />
          <Line type="monotone" dataKey="phri" stroke="var(--cyan)" strokeWidth={1.5}
            dot={false} activeDot={{ r: 4, fill: 'var(--cyan)', stroke: 'var(--bg-card)', strokeWidth: 2 }}
            isAnimationActive animationDuration={1500} animationEasing="ease-out" />
          <Brush dataKey="date" height={20} stroke="var(--border-glow)" fill="var(--bg-void)"
            travellerWidth={6} />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
