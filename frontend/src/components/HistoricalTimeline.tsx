import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Brush
} from 'recharts';
import { motion } from 'framer-motion';
import type { HistoryPoint } from '../api';

interface Props { data: HistoryPoint[] }

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as HistoryPoint;
  return (
    <div style={{ background: 'rgba(17,24,39,0.95)', border: '1px solid #1e2a3d',
      borderRadius: 8, padding: '0.6rem 0.9rem', fontFamily: 'DM Mono', fontSize: '0.78rem' }}>
      <div style={{ color: '#6b7a99', marginBottom: 4 }}>{d.date}</div>
      <div style={{ color: '#00e5ff' }}>PHRI: {d.phri.toFixed(3)}</div>
      <div style={{ color: '#45b7d1' }}>Temp: {d.temp}°C</div>
      <div style={{ color: '#96ceb4' }}>Rain: {d.rain} mm</div>
      <div style={{ color: '#ffeaa7' }}>Humidity: {d.humid}%</div>
    </div>
  );
};

export default function HistoricalTimeline({ data }: Props) {
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
            2023–2024 PHRI Proxy (Weather-based)
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
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="date" tick={{ fill: '#6b7a99', fontSize: 9, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} interval={Math.ceil(sampled.length / 8)} />
          <YAxis domain={[0, 1]} tick={{ fill: '#6b7a99', fontSize: 9, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} tickFormatter={v => v.toFixed(1)} />
          <Tooltip content={<CustomTooltip />} />
          {/* Alert threshold band */}
          <ReferenceLine y={0.70} stroke="rgba(255,76,76,0.4)" strokeDasharray="5 3"
            label={{ value: 'Alert 0.70', fill: '#ff4c4c', fontSize: 9, fontFamily: 'DM Mono', position: 'right' }} />
          <Line type="monotone" dataKey="phri" stroke="#00e5ff" strokeWidth={1.5}
            dot={false} activeDot={{ r: 4, fill: '#00e5ff', stroke: '#111827', strokeWidth: 2 }}
            isAnimationActive animationDuration={1500} animationEasing="ease-out" />
          <Brush dataKey="date" height={20} stroke="#1e2a3d" fill="rgba(17,24,39,0.8)"
            travellerWidth={6} />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
