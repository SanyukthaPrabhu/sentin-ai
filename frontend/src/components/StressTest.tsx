import { useState, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, Legend, ResponsiveContainer
} from 'recharts';
import { motion } from 'framer-motion';
import { api } from '../api';
import type { StressTestData } from '../api';

const BUCKETS: Record<string, string> = {
  dengue_malaria: 'Dengue / Malaria',
  lepto_cholera:  'Lepto / Cholera',
  respiratory:    'Respiratory',
  general_risk:   'General Risk',
  none:           'None',
};

export default function StressTest() {
  const [bucket, setBucket] = useState('dengue_malaria');
  const [data, setData] = useState<StressTestData | null>(null);
  const [loading, setLoading] = useState(false);

  const runTest = async (b: string) => {
    setLoading(true);
    try {
      const res = await api.stressTest(b);
      setData(res);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { runTest(bucket); }, []);

  const chartData = data
    ? data.phri_values.map((v, i) => ({
        phri: v,
        total: data.total_cases[i],
        peak:  data.peak_cases[i],
      }))
    : [];

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <div className="section-label" style={{ borderBottom: 'none', marginBottom: 2 }}>
            Stress Test — PHRI Response Sweep
          </div>
          <div style={{ fontFamily: 'Syne', fontSize: '0.9rem', color: '#e8edf5' }}>
            {data?.disease_label}
          </div>
        </div>
        <select
          className="sidebar-input"
          style={{ width: 'auto', minWidth: 160 }}
          value={bucket}
          onChange={e => { setBucket(e.target.value); runTest(e.target.value); }}
        >
          {Object.entries(BUCKETS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {/* Gradient stress bar */}
      <div className="stress-bar" style={{ height: 6, borderRadius: 3,
        background: 'linear-gradient(90deg, #00e676, #ffb300, #ff4c4c)', marginBottom: '1rem' }} />

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="phri" tick={{ fill: '#6b7a99', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} tickFormatter={v => v.toFixed(1)}
            label={{ value: 'PHRI Score', fill: '#6b7a99', fontSize: 10, position: 'insideBottom', offset: -3 }} />
          <YAxis tick={{ fill: '#6b7a99', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ background: 'rgba(17,24,39,0.95)', border: '1px solid #1e2a3d',
              borderRadius: 8, fontFamily: 'DM Mono', fontSize: '0.78rem' }}
            labelFormatter={v => `PHRI: ${Number(v).toFixed(2)}`} />
          <ReferenceLine x={0.70} stroke="rgba(255,76,76,0.5)" strokeDasharray="4 2"
            label={{ value: 'Alert', fill: '#ff4c4c', fontSize: 9, fontFamily: 'DM Mono', position: 'top' }} />
          <Legend wrapperStyle={{ fontFamily: 'DM Mono', fontSize: '0.75rem', color: '#6b7a99' }} />
          <Line type="monotone" dataKey="total" name="14d Total Cases" stroke="#00e5ff"
            strokeWidth={2} dot={false} isAnimationActive animationDuration={600} />
          <Line type="monotone" dataKey="peak" name="Peak Daily Cases" stroke="#ffb300"
            strokeWidth={2} strokeDasharray="5 3" dot={false} isAnimationActive animationDuration={600} />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
