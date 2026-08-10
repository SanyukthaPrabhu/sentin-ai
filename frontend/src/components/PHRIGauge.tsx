import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface Props {
  score: number;       // 0.0 – 1.0
  riskLevel: string;
}

const RISK_COLORS: Record<string, string> = {
  LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#f97316', CRITICAL: '#ef4444',
};

function phriColor(s: number): string {
  if (s < 0.40) return '#10b981';
  if (s < 0.60) return '#f59e0b';
  if (s < 0.75) return '#f97316';
  return '#ef4444';
}

// SVG arc helper
function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const a = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToXY(cx, cy, r, startDeg);
  const e = polarToXY(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

const CX = 110, CY = 110, R = 85;
const START_DEG = 220, END_DEG = 500; // 280° sweep

export default function PHRIGauge({ score, riskLevel }: Props) {
  const [displayed, setDisplayed] = useState(0);
  const animRef = useRef<number>(0);
  const color = phriColor(score);

  // Count-up animation
  useEffect(() => {
    const start = performance.now();
    const dur = 1200;
    const from = 0;
    const to = score;
    cancelAnimationFrame(animRef.current);
    const step = (now: number) => {
      const t = Math.min((now - start) / dur, 1);
      const ease = 1 - Math.pow(1 - t, 4); // expo-out
      setDisplayed(from + (to - from) * ease);
      if (t < 1) animRef.current = requestAnimationFrame(step);
    };
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [score]);

  const needleDeg = START_DEG + displayed * (END_DEG - START_DEG);
  const needleXY = polarToXY(CX, CY, R - 12, needleDeg);

  // Gradient arc segments
  const segments = [
    { from: 220, to: 332, color: 'rgba(16, 185, 129, 0.12)' },  // LOW
    { from: 332, to: 388, color: 'rgba(245, 158, 11, 0.12)' },  // MEDIUM
    { from: 388, to: 430, color: 'rgba(249, 115, 22, 0.12)' },  // HIGH
    { from: 430, to: 500, color: 'rgba(239, 68, 68, 0.12)' },   // CRITICAL
  ];

  const badgeClass = riskLevel.toLowerCase();

  return (
    <div className="card shimmer" style={{ textAlign: 'center', padding: '1.5rem 1rem 1rem' }}>
      <div className="section-label" style={{ borderBottom: 'none', marginBottom: '0.5rem' }}>
        Public Health Risk Index
      </div>

      <svg viewBox="0 0 220 145" style={{ width: '100%', maxWidth: 260, overflow: 'visible' }}>
        {/* Background segments */}
        {segments.map((seg, i) => (
          <path
            key={i}
            d={arcPath(CX, CY, R, seg.from, seg.to)}
            fill="none"
            stroke={seg.color}
            strokeWidth={18}
            strokeLinecap="round"
          />
        ))}

        {/* Track */}
        <path
          d={arcPath(CX, CY, R, START_DEG, END_DEG)}
          fill="none"
          stroke="var(--border-hover)"
          strokeWidth={6}
          strokeLinecap="round"
        />

        {/* Animated fill arc */}
        <path
          d={arcPath(CX, CY, R, START_DEG, START_DEG + displayed * (END_DEG - START_DEG))}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
        />

        {/* Tick marks */}
        {[0, 0.4, 0.6, 0.75, 1.0].map((v, i) => {
          const d = START_DEG + v * (END_DEG - START_DEG);
          const outer = polarToXY(CX, CY, R + 6, d);
          const inner = polarToXY(CX, CY, R - 6, d);
          return (
            <line key={i} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
              stroke="var(--border-hover)" strokeWidth={1.5} />
          );
        })}

        {/* Tick labels */}
        {[0, 0.4, 0.6, 0.75, 1.0].map((v, i) => {
          const d = START_DEG + v * (END_DEG - START_DEG);
          const pos = polarToXY(CX, CY, R + 16, d);
          return (
            <text key={i} x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="middle"
              fontSize="8.5" fill="var(--text-muted)" fontFamily="DM Mono">{v}</text>
          );
        })}

        {/* Needle */}
        <line
          x1={CX} y1={CY}
          x2={needleXY.x} y2={needleXY.y}
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
        />

        {/* Centre dot */}
        <circle cx={CX} cy={CY} r={4.5} fill={color} />

        {/* Score text */}
        <text x={CX} y={CY - 10} textAnchor="middle" dominantBaseline="middle"
          fontSize="28" fontWeight="700" fontFamily="DM Sans" fill="var(--text-primary)">
          {displayed.toFixed(2)}
        </text>
        <text x={CX} y={CY + 22} textAnchor="middle" fontSize="9.5" fill="var(--text-muted)" fontFamily="DM Mono">
          / 1.00
        </text>
      </svg>

      <motion.div
        className={`badge badge-${badgeClass}`}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1, duration: 0.3 }}
      >
        {riskLevel}
      </motion.div>
    </div>
  );
}
