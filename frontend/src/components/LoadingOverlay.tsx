import { motion } from 'framer-motion';

const STEPS = [
  'Fetching live weather…',
  'Querying GEE satellite…',
  'Running YOLO inference…',
  'Computing PHRI score…',
  'Generating AI bulletin…',
];

interface Props {
  step: number;   // 0-4 (current step index, -1 = done)
  visible: boolean;
}

export default function LoadingOverlay({ step, visible }: Props) {
  if (!visible) return null;

  const label = step >= 0 && step < STEPS.length ? STEPS[step] : 'Processing…';

  return (
    <div className="loading-overlay">
      {/* Orbiting satellite */}
      <div style={{ position: 'relative', width: 100, height: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Globe rings */}
        <div style={{ position: 'absolute', width: 70, height: 70, border: '1px solid rgba(var(--cyan-rgb), 0.15)',
          borderRadius: '50%' }} />
        <div style={{ position: 'absolute', width: 50, height: 50, border: '1px solid rgba(var(--cyan-rgb), 0.1)',
          borderRadius: '50%' }} />
        {/* Globe icon */}
        <div style={{ fontSize: '2rem', zIndex: 1 }}>🌏</div>
        {/* Orbiting dot */}
        <div className="orbit-sat" style={{ position: 'absolute' }} />
      </div>

      {/* Step label */}
      <motion.div
        key={label}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.4 }}
        style={{ fontFamily: 'DM Sans', fontSize: '0.85rem', fontWeight: 600, color: 'var(--cyan)' }}
      >
        {label}
      </motion.div>

      {/* Status bar */}
      <div className="status-bar" style={{ width: 280 }}>
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={`status-seg ${i < step ? 'done' : i === step ? 'active' : ''}`}
          />
        ))}
      </div>

      {/* Sub-text */}
      <div style={{ fontFamily: 'DM Mono', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        Sentin-AI · Real-time pipeline
      </div>
    </div>
  );
}
