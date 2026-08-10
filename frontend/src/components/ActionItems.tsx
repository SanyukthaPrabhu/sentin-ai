import { motion } from 'framer-motion';
import type { DiseaseData } from '../api';

interface Props {
  disease: DiseaseData;
  actionItems: string[];
}

export default function ActionItems({ disease, actionItems }: Props) {
  const isNone = disease.primary_bucket === 'none';

  return (
    <div>
      <div className="section-label">Action Items</div>

      {/* Action item list */}
      {actionItems.length > 0 ? (
        actionItems.map((item, i) => (
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
        ))
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', padding: '0.5rem 0' }}>
          No specific actions required at current risk level.
        </div>
      )}

      {/* Disease info box — only when an actual disease bucket is matched */}
      {isNone ? (
        <motion.div
          className="officer-note"
          style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <span style={{ fontSize: '1.2rem' }}>✅</span>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--green)', marginBottom: '0.15rem' }}>
              No Active Disease Vectors
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Environmental conditions are within safe thresholds. Continue routine hygiene practices and monitor local health advisories.
            </div>
          </div>
        </motion.div>
      ) : (
        <motion.div
          className="officer-note"
          style={{ marginTop: '1rem' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <div style={{ marginBottom: '0.4rem', display: 'flex', gap: '0.4rem', alignItems: 'baseline' }}>
            <strong style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', minWidth: 90 }}>Vector</strong>
            <span style={{ color: 'var(--cyan)', fontSize: '0.85rem' }}>{disease.vector}</span>
          </div>
          <div style={{ marginBottom: '0.4rem', display: 'flex', gap: '0.4rem', alignItems: 'baseline' }}>
            <strong style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', minWidth: 90 }}>Incubation</strong>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{disease.incubation_days}</span>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'baseline' }}>
            <strong style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', minWidth: 90 }}>Warning Signs</strong>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{disease.warning_signs}</span>
          </div>
        </motion.div>
      )}

      {/* Rules Triggered / Co-Risk — only when relevant */}
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
                    {r.replace(/_/g, ' ')}
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
                <span key={b} className="rule-chip" style={{
                  borderColor: 'rgba(245,158,11,0.3)',
                  background: 'rgba(245,158,11,0.06)',
                  color: 'var(--amber)',
                }}>
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
