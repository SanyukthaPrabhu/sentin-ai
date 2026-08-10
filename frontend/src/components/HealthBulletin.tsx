import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import type { BulletinData } from '../api';

interface Props { bulletin: BulletinData; }

// Word-by-word typewriter reveal, capped at 1.5s total
function TypewriterText({ text }: { text: string }) {
  const words = text.split(/(\s+)/);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    setShown(0);
    if (!words.length) return;
    const delay = Math.min(1500 / words.length, 40);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setShown(i);
      if (i >= words.length) clearInterval(interval);
    }, delay);
    return () => clearInterval(interval);
  }, [text]);

  return (
    <span>
      {words.slice(0, shown).join('')}
      {shown < words.length && <span style={{ opacity: 0.5 }}>|</span>}
    </span>
  );
}

export default function HealthBulletin({ bulletin }: Props) {
  const paragraphs = bulletin.health_bulletin.split(/\n\n+/);

  return (
    <motion.div
      className="bulletin-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* AI / Template badge */}
      <div style={{ position: 'absolute', top: '1rem', right: '1rem' }}>
        <span style={{
          fontFamily: 'DM Mono', fontSize: '0.65rem', padding: '0.15rem 0.5rem',
          borderRadius: 4, border: `1px solid ${bulletin.fallback_used ? 'rgba(107,122,153,0.3)' : 'rgba(124,92,255,0.4)'}`,
          color: bulletin.fallback_used ? '#6b7a99' : '#7c5cff',
          background: bulletin.fallback_used ? 'transparent' : 'rgba(124,92,255,0.08)',
        }}>
          {bulletin.fallback_used ? 'Template' : 'Groq LLM'}
        </span>
      </div>

      <div className="bulletin-headline" style={{ paddingRight: '6rem' }}>
        📰 {bulletin.headline}
      </div>

      <div className="bulletin-body">
        {paragraphs.map((para, i) => (
          <p key={i} style={{ marginBottom: i < paragraphs.length - 1 ? '1rem' : 0 }}>
            {i === 0 ? <TypewriterText text={para} /> : para}
          </p>
        ))}
      </div>

      <div className="officer-note">
        🔬 <strong style={{ color: 'var(--text-primary)' }}>Officer Note:</strong>{' '}
        {bulletin.officer_note}
      </div>

      <div style={{ fontFamily: 'DM Mono', fontSize: '0.65rem', color: 'var(--text-muted)',
        marginTop: '0.75rem', textAlign: 'right' }}>
        Generated: {bulletin.generated_date}
      </div>
    </motion.div>
  );
}
