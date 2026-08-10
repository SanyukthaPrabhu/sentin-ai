import { motion } from 'framer-motion';
import type { LocationConfig } from '../api';

const QUICK_CITIES: (LocationConfig & { name: string; desc: string; icon: string })[] = [
  { name: 'Bengaluru', lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka', desc: 'Suburban lake beds & stagnant water tracking.', icon: '🏢' },
  { name: 'Mumbai', lat: 19.07, lon: 72.87, radius_km: 5, location_name: 'Mumbai, Maharashtra', desc: 'Monsoon precipitation & urban garbage pile risk.', icon: '🌊' },
  { name: 'Chennai', lat: 13.08, lon: 80.27, radius_km: 5, location_name: 'Chennai, Tamil Nadu', desc: 'Coastal vegetation dynamics & high humidity risk.', icon: '🌴' },
  { name: 'Las Vegas', lat: 36.17, lon: -115.14, radius_km: 5, location_name: 'Las Vegas, Nevada', desc: 'Arid climate control backtest (dry environment proxy).', icon: '🌵' },
];

const PIPELINE_NODES = [
  { icon: '🛰️', label: '1. GEE Remote Sensing', sub: 'Sentinel-2 imagery fetch' },
  { icon: '👁️', label: '2. YOLOv8 Segmentation', sub: 'Water, waste & vegetation' },
  { icon: '🧠', label: '3. LSTM Temporal Net', sub: 'PHRI risk index scoring' },
  { icon: '📈', label: '4. SEIR Outbreak Engine', sub: '14-day case projections' },
];

const FEATURE_CARDS = [
  {
    icon: '🌡️',
    title: 'NASA POWER Weather',
    desc: 'Live precipitation, humidity, dew point, and insolation from the NASA POWER API updated hourly.',
  },
  {
    icon: '🗺️',
    title: 'Earth Observation',
    desc: 'Google Earth Engine Sentinel-2 band composites detect surface changes over the target radius.',
  },
  {
    icon: '📊',
    title: 'LSTM Sequence Prediction',
    desc: 'A trained 30-day sliding window model outputs daily PHRI scores from combined sensor inputs.',
  },
  {
    icon: '🔬',
    title: 'IDSP-Aligned Labels',
    desc: 'Disease outbreak windows align to IDSP weekly bulletins — model ground truth from the field.',
  },
];

interface Props {
  onStartSurveillance: (city: LocationConfig) => void;
  onNavigateToStress: () => void;
  theme: 'dark' | 'light';
}

export default function LandingPage({ onStartSurveillance, onNavigateToStress, theme }: Props) {
  const isDark = theme === 'dark';
  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>

      {/* ── Hero ── */}
      <motion.div
        className="landing-hero"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
          background: isDark ? 'rgba(14,165,233,0.08)' : 'rgba(2,132,199,0.08)',
          border: '1px solid rgba(var(--cyan-rgb), 0.2)',
          borderRadius: 20, padding: '0.3rem 0.9rem',
          fontSize: '0.75rem', fontFamily: 'DM Mono', color: 'var(--cyan)',
          marginBottom: '1.25rem',
        }}>
          <span className="ping-dot" style={{ width: 6, height: 6 }} />
          Live pipeline · ROC-AUC 0.8005 · 701 sequences evaluated
        </div>

        <h1 className="landing-title">
          Autonomous Epidemiological<br />Intelligence Platform
        </h1>

        <p className="landing-tagline">
          Sentin-AI fuses satellite imagery, YOLOv8 computer vision, and LSTM temporal modelling
          to forecast vector-borne disease risk — days before outbreaks surface.
        </p>

        <div className="landing-actions">
          <motion.button
            className="btn btn-primary"
            onClick={() => onStartSurveillance(QUICK_CITIES[0])}
            style={{ padding: '0.75rem 1.5rem', fontSize: '0.9rem' }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            🛰️ Enter Surveillance Hub
          </motion.button>
          <motion.button
            className="btn btn-secondary"
            onClick={onNavigateToStress}
            style={{ padding: '0.75rem 1.5rem', fontSize: '0.9rem' }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            🧪 Stress Simulation
          </motion.button>
        </div>
      </motion.div>

      {/* ── Pipeline Diagram ── */}
      <motion.div
        className="landing-map-container"
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
      >
        <div className="section-label" style={{ borderBottom: 'none', marginBottom: '1.25rem' }}>
          Platform Pipeline Architecture
        </div>
        <div className="pipeline-diagram">
          {PIPELINE_NODES.map((node, i) => (
            <>
              <motion.div
                key={node.label}
                className="pipeline-node"
                whileHover={{ borderColor: 'var(--cyan)', y: -2 }}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.07 }}
              >
                <div className="pipeline-node-icon">{node.icon}</div>
                <div className="pipeline-node-label">{node.label}</div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{node.sub}</span>
              </motion.div>
              {i < PIPELINE_NODES.length - 1 && <div className="pipeline-connector" />}
            </>
          ))}
        </div>
      </motion.div>

      {/* ── Feature Cards ── */}
      <div style={{ maxWidth: 1000, margin: '0 auto 3rem', padding: '0 1rem' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem', fontWeight: 700 }}>
          System Capabilities
        </h2>
        <div className="landing-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {FEATURE_CARDS.map((card, i) => (
            <motion.div
              key={card.title}
              className="landing-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 + i * 0.06 }}
            >
              <div className="landing-card-icon">{card.icon}</div>
              <div className="landing-card-title">{card.title}</div>
              <div className="landing-card-desc">{card.desc}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Quick Launch ── */}
      <div style={{ maxWidth: 1000, margin: '0 auto 4rem', padding: '0 1rem' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem', fontWeight: 700 }}>
          Launch Target Surveillance
        </h2>
        <div className="landing-grid">
          {QUICK_CITIES.map((c, i) => (
            <motion.div
              key={c.name}
              className="landing-card"
              onClick={() => onStartSurveillance(c)}
              style={{ cursor: 'pointer' }}
              whileHover={{ scale: 1.02, borderColor: 'var(--border-hover)' }}
              whileTap={{ scale: 0.98 }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + i * 0.06 }}
            >
              <div className="landing-card-icon">{c.icon}</div>
              <div className="landing-card-title">{c.name}</div>
              <div className="landing-card-desc">{c.desc}</div>
              <div style={{
                marginTop: '1rem', fontSize: '0.75rem', fontWeight: 600,
                color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: '0.3rem'
              }}>
                Inspect Region <span style={{ fontSize: '1rem' }}>→</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

    </div>
  );
}
