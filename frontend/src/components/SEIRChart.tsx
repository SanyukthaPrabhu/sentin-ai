import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';

interface Props {
  newCasesCurve: number[];
  peakCases: number;
  peakDay: number;
  totalProjected: number;
  diseaseLabel: string;
  phriScore: number;
}

function phriColor(s: number) {
  if (s < 0.40) return '#10b981';
  if (s < 0.60) return '#f59e0b';
  if (s < 0.75) return '#f97316';
  return '#ef4444';
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-glow)',
      borderRadius: 8, padding: '0.5rem 0.75rem', fontFamily: 'DM Mono', fontSize: '0.78rem' }}>
      <div style={{ color: 'var(--text-muted)' }}>Day {label}</div>
      <div style={{ color: 'var(--text-primary)', marginTop: 2 }}>{Math.round(payload[0].value)} new cases</div>
    </div>
  );
};

export default function SEIRChart({ newCasesCurve, peakCases, peakDay, totalProjected, diseaseLabel, phriScore }: Props) {
  const color = phriColor(phriScore);
  const data = newCasesCurve.map((v, i) => ({ day: i + 1, cases: Math.round(v) }));
  const gradId = 'seir-grad';

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
            14-Day Case Projection
          </div>
          <div style={{ fontFamily: 'DM Sans', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {diseaseLabel}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'DM Mono', fontSize: '0.7rem', color: 'var(--text-muted)' }}>Total Projected</div>
          <div style={{ fontFamily: 'DM Sans', fontSize: '1.4rem', fontWeight: 800, color }}>{totalProjected.toLocaleString()}</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
              <stop offset="95%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-glow)" />
          <XAxis dataKey="day" tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} label={{ value: 'Day', fill: 'var(--text-muted)', fontSize: 10, position: 'insideBottom', offset: -2 }} />
          <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} animationDuration={200} />
          <ReferenceLine x={peakDay} stroke={color} strokeDasharray="4 2" strokeWidth={1.5}
            label={{ value: `Peak: ${peakCases}`, fill: color, fontSize: 10, fontFamily: 'DM Mono', position: 'top' }} />
          <Area type="monotone" dataKey="cases" stroke={color} strokeWidth={2.5}
            fill={`url(#${gradId})`} dot={false}
            activeDot={{ r: 5, fill: color, stroke: 'var(--bg-card)', strokeWidth: 2 }}
            isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
