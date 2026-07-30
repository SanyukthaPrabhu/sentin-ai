import { motion } from 'framer-motion';
import type { DiseaseData } from '../api';

interface Props {
  disease: DiseaseData;
  actionItems: string[];
}

export default function ActionItems({ disease, actionItems }: Props) {
  return (
    <div>
      <div className="section-label">Action Items</div>
      {actionItems.map((item, i) => (
        <motion.div
          key={i}
          className="action-item"
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="action-dot">▸</span>
          <span style={{ fontSize: '0.85rem' }}>{item}</span>
        </motion.div>
      ))}

      <motion.div
        className="officer-note"
        style={{ marginTop: '1rem' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <div style={{ marginBottom: '0.35rem' }}>
          <strong style={{ color: '#e8edf5' }}>Vector:</strong>{' '}
          <span style={{ color: '#00e5ff' }}>{disease.vector}</span>
        </div>
        <div style={{ marginBottom: '0.35rem' }}>
          <strong style={{ color: '#e8edf5' }}>Incubation:</strong>{' '}
          {disease.incubation_days}
        </div>
        <div>
          <strong style={{ color: '#e8edf5' }}>Warning Signs:</strong>{' '}
          {disease.warning_signs}
        </div>
      </motion.div>

      {(disease.rules_triggered.length > 0 || disease.secondary_buckets.length > 0) && (
        <motion.div
          className="card"
          style={{ marginTop: '1rem', padding: '1rem' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          {disease.rules_triggered.length > 0 && (
            <>
              <div className="section-label" style={{ borderBottom: 'none', marginBottom: '0.4rem' }}>
                Rules Triggered
              </div>
              <div>
                {disease.rules_triggered.map((r, i) => (
                  <motion.span
                    key={r}
                    className="rule-chip"
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 + i * 0.06, type: 'spring', stiffness: 300, damping: 20 }}
                  >
                    {r}
                  </motion.span>
                ))}
              </div>
            </>
          )}
          {disease.secondary_buckets.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <div className="section-label" style={{ borderBottom: 'none', marginBottom: '0.4rem' }}>
                Co-Risk Buckets
              </div>
              {disease.secondary_buckets.map(b => (
                <span key={b} className="rule-chip" style={{ borderColor: 'rgba(255,179,0,0.3)',
                  background: 'rgba(255,179,0,0.06)', color: '#ffb300' }}>
                  {b.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
