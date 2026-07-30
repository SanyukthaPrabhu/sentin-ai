import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface Props {
  score: number;       // 0.0 – 1.0
  riskLevel: string;
}

const RISK_COLORS: Record<string, string> = {
  LOW: '#00e676', MEDIUM: '#ffb300', HIGH: '#ff6400', CRITICAL: '#ff4c4c',
};

function phriColor(s: number): string {
  if (s < 0.40) return '#00e676';
  if (s < 0.60) return '#ffb300';
  if (s < 0.75) return '#ff6400';
  return '#ff4c4c';
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
    { from: 220, to: 332, color: 'rgba(0,230,118,0.2)' },   // LOW
    { from: 332, to: 388, color: 'rgba(255,179,0,0.2)' },   // MEDIUM
    { from: 388, to: 430, color: 'rgba(255,100,0,0.2)' },   // HIGH
    { from: 430, to: 500, color: 'rgba(255,76,76,0.22)' },  // CRITICAL
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
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={6}
          strokeLinecap="round"
        />

        {/* Animated fill arc */}
        <motion.path
          d={arcPath(CX, CY, R, START_DEG, START_DEG + score * (END_DEG - START_DEG))}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
          filter="url(#glow)"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* Tick marks */}
        {[0, 0.4, 0.6, 0.75, 1.0].map((v, i) => {
          const d = START_DEG + v * (END_DEG - START_DEG);
          const outer = polarToXY(CX, CY, R + 6, d);
          const inner = polarToXY(CX, CY, R - 6, d);
          return (
            <line key={i} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
              stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
          );
        })}

        {/* Tick labels */}
        {[0, 0.4, 0.6, 0.75, 1.0].map((v, i) => {
          const d = START_DEG + v * (END_DEG - START_DEG);
          const pos = polarToXY(CX, CY, R + 16, d);
          return (
            <text key={i} x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="middle"
              fontSize="8" fill="#6b7a99" fontFamily="DM Mono">{v}</text>
          );
        })}

        {/* Needle */}
        <motion.line
          x1={CX} y1={CY}
          x2={needleXY.x} y2={needleXY.y}
          stroke={color}
          strokeWidth={2}
          strokeLinecap="round"
          filter="url(#glow)"
          initial={{ rotate: START_DEG - 90, originX: CX, originY: CY }}
          animate={{ rotate: needleDeg - 90 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* Centre dot */}
        <circle cx={CX} cy={CY} r={5} fill={color} filter="url(#glow)" />

        {/* Score text */}
        <text x={CX} y={CY - 10} textAnchor="middle" dominantBaseline="middle"
          fontSize="30" fontWeight="800" fontFamily="Syne" fill={color}>
          {displayed.toFixed(2)}
        </text>
        <text x={CX} y={CY + 22} textAnchor="middle" fontSize="9" fill="#6b7a99" fontFamily="DM Mono">
          / 1.00
        </text>

        {/* Glow filter */}
        <defs>
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
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
