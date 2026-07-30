import { useState } from 'react';
import { motion } from 'framer-motion';
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

function SatImage({ b64, caption }: { b64: string | null; caption: string }) {
  const [scanned, setScanned] = useState(false);

  return (
    <div className="card" style={{ padding: '0.75rem', overflow: 'hidden' }}>
      <div style={{ position: 'relative', background: '#000', borderRadius: 8, overflow: 'hidden', minHeight: 180 }}>
        {b64 ? (
          <>
            <motion.img
              src={`data:image/png;base64,${b64}`}
              alt={caption}
              style={{ width: '100%', display: 'block', borderRadius: 8 }}
              className="scan-reveal"
              onAnimationEnd={() => setScanned(true)}
            />
            {!scanned && <div className="scan-line" />}
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 180, color: '#6b7a99', fontFamily: 'DM Mono', fontSize: '0.8rem' }}>
            Pending fetch…
          </div>
        )}
      </div>
      <div style={{ fontFamily: 'DM Mono', fontSize: '0.7rem', color: '#6b7a99',
        marginTop: '0.5rem', textAlign: 'center' }}>{caption}</div>
    </div>
  );
}

export default function SatellitePanel({ rgbB64, ndwiB64, meta, locationName, lat, lon, radiusKm }: Props) {
  return (
    <div className="grid-3" style={{ alignItems: 'start' }}>
      <SatImage b64={rgbB64} caption={`True Color RGB${meta?.date ? ` (${meta.date})` : ''}`} />
      <SatImage b64={ndwiB64} caption={`NDWI Water Index${meta?.date ? ` (${meta.date})` : ''}`} />

      <motion.div
        className="card"
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="metric-title">Satellite Metadata</div>
        <div style={{ fontFamily: 'DM Mono', fontSize: '0.8rem', color: '#00e5ff',
          marginTop: '0.75rem', lineHeight: 2 }}>
          <div>📍 {locationName}</div>
          <div style={{ color: '#6b7a99' }}>({lat}°N, {lon}°E)</div>
          <div style={{ color: '#e8edf5', marginTop: '0.5rem' }}>📏 Radius: {radiusKm} km</div>
          {meta && (
            <>
              <div>📅 Scene: {meta.date}</div>
              <div>☁️ Cloud: {meta.cloud_pct}%</div>
              <div>💧 NDWI: {typeof meta.ndwi_mean === 'number' ? meta.ndwi_mean.toFixed(4) : meta.ndwi_mean}</div>
              <div>🌿 NDVI: {typeof meta.ndvi_mean === 'number' ? meta.ndvi_mean.toFixed(4) : meta.ndvi_mean}</div>
            </>
          )}
          {!meta && (
            <div style={{ color: '#6b7a99', marginTop: '0.5rem' }}>No imagery loaded yet.</div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
