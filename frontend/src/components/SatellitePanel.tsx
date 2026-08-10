import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { LiveMeta } from '../api';

interface Props {
  rgbB64: string | null;
  ndwiB64: string | null;
  meta: LiveMeta | null;
  locationName: string;
  lat: number;
  lon: number;
  radiusKm: number;
}

function SatImage({ b64, caption, loading }: { b64: string | null; caption: string; loading?: boolean }) {
  const [scanned, setScanned] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Reset states when image changes
  useEffect(() => {
    setImageLoaded(false);
    setScanned(false);
  }, [b64]);

  return (
    <motion.div 
      className="card" 
      style={{ padding: '0.75rem', overflow: 'hidden' }}
      whileHover={{ y: -4, scale: 1.01, boxShadow: '0 6px 16px rgba(0,0,0,0.08)' }}
      transition={{ duration: 0.25 }}
    >
      <div style={{ position: 'relative', background: 'var(--bg-void)', borderRadius: 8, overflow: 'hidden', minHeight: 180 }}>
        <AnimatePresence mode="wait">
          {b64 && !loading ? (
            <motion.div
              key="image-container"
              style={{ position: 'relative', width: '100%', height: '100%' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <motion.img
                src={`data:image/png;base64,${b64}`}
                alt={caption}
                style={{ width: '100%', display: 'block', borderRadius: 8 }}
                initial={{ scale: 1.08, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] as const }}
                onLoad={() => setImageLoaded(true)}
                className="scan-reveal"
                onAnimationEnd={() => setScanned(true)}
              />
              {imageLoaded && !scanned && <div className="scan-line" />}
            </motion.div>
          ) : (
            <motion.div
              key="shimmer-placeholder"
              className="loading-shimmer-box"
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: 180,
                width: '100%',
                borderRadius: 8
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="shimmer-line-pulse" style={{ 
                width: 28, height: 28, borderRadius: '50%', 
                border: '2px solid var(--border-glow)', 
                borderTopColor: 'var(--cyan)',
                animation: 'radarPing 1.2s linear infinite',
                marginBottom: '0.5rem'
              }} />
              <div style={{ color: 'var(--text-muted)', fontFamily: 'DM Mono', fontSize: '0.78rem' }}>
                Fetching Sentinel scene…
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div style={{ fontFamily: 'DM Mono', fontSize: '0.7rem', color: 'var(--text-muted)',
        marginTop: '0.5rem', textAlign: 'center' }}>{caption}</div>
    </motion.div>
  );
}

export default function SatellitePanel({ rgbB64, ndwiB64, meta, locationName, lat, lon, radiusKm }: Props) {
  // Stagger wrapper settings
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 15 },
    show: { 
      opacity: 1, 
      y: 0,
      transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const }
    }
  };

  return (
    <motion.div 
      className="grid-3" 
      style={{ alignItems: 'start' }}
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants}>
        <SatImage b64={rgbB64} caption={`True Color RGB${meta?.date ? ` (${meta.date})` : ''}`} />
      </motion.div>
      <motion.div variants={itemVariants}>
        <SatImage b64={ndwiB64} caption={`NDWI Water Index${meta?.date ? ` (${meta.date})` : ''}`} />
      </motion.div>

      <motion.div
        className="card"
        variants={itemVariants}
        whileHover={{ y: -4, scale: 1.01, boxShadow: '0 6px 16px rgba(0,0,0,0.08)' }}
        transition={{ duration: 0.25 }}
      >
        <div className="metric-title" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>Satellite Metadata</div>
        <div style={{ fontFamily: 'DM Mono', fontSize: '0.8rem', color: 'var(--cyan)',
          marginTop: '0.75rem', lineHeight: 2 }}>
          <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>📍 {locationName}</div>
          <div style={{ color: 'var(--text-muted)' }}>({lat}°N, {lon}°E)</div>
          <div style={{ color: 'var(--text-primary)', marginTop: '0.5rem' }}>📏 Radius: {radiusKm} km</div>
          {meta ? (
            <>
              <div style={{ color: 'var(--text-primary)' }}>📅 Scene: {meta.date}</div>
              <div style={{ color: 'var(--text-primary)' }}>☁️ Cloud: {meta.cloud_pct}%</div>
              <div style={{ color: 'var(--text-primary)' }}>💧 NDWI: {typeof meta.ndwi_mean === 'number' ? meta.ndwi_mean.toFixed(4) : meta.ndwi_mean}</div>
              <div style={{ color: 'var(--text-primary)' }}>🌿 NDVI: {typeof meta.ndvi_mean === 'number' ? meta.ndvi_mean.toFixed(4) : meta.ndvi_mean}</div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>No imagery loaded yet.</div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
