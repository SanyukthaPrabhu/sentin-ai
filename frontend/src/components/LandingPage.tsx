import { Fragment, lazy, Suspense } from 'react';
import { motion } from 'framer-motion';
import type { LocationConfig } from '../api';

// Lazy load the 3D globe component
const LandingHeroGlobe = lazy(() => import('./LandingHeroGlobe'));

const QUICK_CITIES: (LocationConfig & { name: string; desc: string; icon: string })[] = [
  { name: 'Bengaluru', lat: 12.98, lon: 77.58, radius_km: 5, location_name: 'Bengaluru, Karnataka', desc: 'Suburban lake beds & stagnant water tracking.', icon: '🏢' },
  { name: 'Mumbai', lat: 19.07, lon: 72.87, radius_km: 5, location_name: 'Mumbai, Maharashtra', desc: 'Monsoon precipitation & urban garbage pile risk.', icon: '🌊' },
  { name: 'Chennai', lat: 13.08, lon: 80.27, radius_km: 5, location_name: 'Chennai, Tamil Nadu', desc: 'Coastal vegetation dynamics & high humidity risk.', icon: '🌴' },
  { name: 'Kolkata', lat: 22.57, lon: 88.36, radius_km: 5, location_name: 'Kolkata, West Bengal', desc: 'River delta flooding & dense urban disease vectors.', icon: '🌿' },
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

      {/* ── Responsive Split Hero Section ── */}
      <div className="hero-split-container" style={{
        maxWidth: 1100,
        margin: '2rem auto 0',
        padding: '0 1.5rem',
        display: 'grid',
        gridTemplateColumns: '1.2fr 1fr',
        gap: '2rem',
        alignItems: 'center'
      }}>
        {/* Left Side: Typography and CTA */}
        <motion.div
          className="landing-hero"
          style={{ textAlign: 'left', padding: '1rem 0', margin: 0 }}
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Breathing live stats pill */}
          <div 
            className="breathing-pill"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
              background: isDark ? 'rgba(14,165,233,0.06)' : 'rgba(2,132,199,0.06)',
              border: '1px solid rgba(var(--cyan-rgb), 0.18)',
              borderRadius: 20, padding: '0.35rem 0.9rem',
              fontSize: '0.75rem', fontFamily: 'DM Mono', color: 'var(--cyan)',
              marginBottom: '1.5rem',
            }}
          >
            <span className="ping-dot" style={{ width: 6, height: 6 }} />
            Live pipeline · ROC-AUC 0.8005 · 701 sequences evaluated
          </div>

          <h1 className="landing-title" style={{ fontSize: '2.5rem', lineHeight: '1.15', marginBottom: '1.25rem' }}>
            Autonomous<br />Epidemiological<br />Intelligence
          </h1>

          <p className="landing-tagline" style={{ margin: '0 0 2rem 0', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
            Sentin-AI fuses Sentinel-2 GEE remote sensing, YOLOv8 computer vision, and deep LSTM temporal sequences to predict disease outbreak windows before they manifest.
          </p>

          <div className="landing-actions" style={{ display: 'flex', gap: '0.75rem' }}>
            <motion.button
              className="btn btn-primary"
              onClick={() => onStartSurveillance(QUICK_CITIES[0])}
              style={{ padding: '0.8rem 1.6rem', fontSize: '0.88rem', fontWeight: 600 }}
              whileHover={{ scale: 1.025, boxShadow: isDark ? '0 0 15px rgba(14,165,233,0.25)' : '0 0 12px rgba(2,132,199,0.15)' }}
              whileTap={{ scale: 0.97 }}
            >
              📡 Enter Surveillance Hub
            </motion.button>
            <motion.button
              className="btn btn-secondary"
              onClick={onNavigateToStress}
              style={{ padding: '0.8rem 1.6rem', fontSize: '0.88rem', fontWeight: 600 }}
              whileHover={{ scale: 1.025 }}
              whileTap={{ scale: 0.97 }}
            >
              🧪 Stress Simulation
            </motion.button>
          </div>
        </motion.div>

        {/* Right Side: Lazy 3D Globe with loading skeleton placeholder */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          style={{ width: '100%', minHeight: 360, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Suspense fallback={
            <div style={{
              width: 260, height: 260, borderRadius: '50%',
              border: '2px dashed var(--border-glow)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', fontFamily: 'DM Mono', fontSize: '0.75rem',
              animation: 'shimmerSweep 1.5s infinite linear'
            }}>
              Loading 3D Globe...
            </div>
          }>
            <LandingHeroGlobe />
          </Suspense>
        </motion.div>
      </div>

      {/* ── Pipeline Diagram ── */}
      <motion.div
        className="landing-map-container"
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        style={{ marginTop: '2rem' }}
      >
        <div className="section-label" style={{ borderBottom: 'none', marginBottom: '1.5rem', textAlign: 'center' }}>
          Platform Pipeline Architecture
        </div>
        <div className="pipeline-diagram" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          {PIPELINE_NODES.map((node, i) => (
            <Fragment key={node.label}>
              <motion.div
                className="pipeline-node"
                whileHover={{ borderColor: 'var(--cyan)', y: -3, boxShadow: '0 4px 12px rgba(var(--cyan-rgb), 0.05)' }}
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="pipeline-node-icon">{node.icon}</div>
                <div className="pipeline-node-label">{node.label}</div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{node.sub}</span>
              </motion.div>
              
              {/* Flow connector with moving light dot */}
              {i < PIPELINE_NODES.length - 1 && (
                <div className="pipeline-connector-container" style={{ display: 'flex', alignItems: 'center' }}>
                  <svg width="45" height="12" viewBox="0 0 45 12" style={{ overflow: 'visible' }}>
                    <path d="M0,6 L45,6" stroke="var(--border-glow)" strokeWidth="1.5" fill="none" />
                    <path 
                      className="pulse-path" 
                      d="M0,6 L45,6" 
                      stroke="var(--cyan)" 
                      strokeWidth="2" 
                      fill="none" 
                      strokeDasharray="6 20" 
                    />
                  </svg>
                </div>
              )}
            </Fragment>
          ))}
        </div>
      </motion.div>

      {/* ── Feature Cards ── */}
      <div style={{ maxWidth: 1000, margin: '4rem auto 3rem', padding: '0 1rem' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: '1.25rem', fontWeight: 700 }}>
          System Capabilities
        </h2>
        <div className="landing-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
          {FEATURE_CARDS.map((card, i) => (
            <motion.div
              key={card.title}
              className="landing-card"
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ y: -4, scale: 1.01, borderColor: 'var(--border-hover)', boxShadow: '0 6px 16px rgba(0,0,0,0.08)' }}
            >
              <div className="landing-card-icon">{card.icon}</div>
              <div className="landing-card-title">{card.title}</div>
              <div className="landing-card-desc" style={{ color: 'var(--text-secondary)' }}>{card.desc}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Quick Launch ── */}
      <div style={{ maxWidth: 1000, margin: '0 auto 4rem', padding: '0 1rem' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: '1.25rem', fontWeight: 700 }}>
          Launch Target Surveillance
        </h2>
        <div className="landing-grid" style={{ gap: '1.25rem' }}>
          {QUICK_CITIES.map((c, i) => (
            <motion.div
              key={c.name}
              className="landing-card"
              onClick={() => onStartSurveillance(c)}
              style={{ cursor: 'pointer' }}
              whileHover={{ y: -4, scale: 1.01, borderColor: 'var(--cyan)', boxShadow: '0 6px 16px rgba(var(--cyan-rgb), 0.04)' }}
              whileTap={{ scale: 0.98 }}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="landing-card-icon">{c.icon}</div>
              <div className="landing-card-title">{c.name}</div>
              <div className="landing-card-desc" style={{ color: 'var(--text-secondary)' }}>{c.desc}</div>
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
