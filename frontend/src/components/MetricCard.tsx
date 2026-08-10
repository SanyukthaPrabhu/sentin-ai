import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

interface Props {
  title: string;
  value: string | number;
  sub?: string;
  color?: string;
  delay?: number;
  numeric?: boolean; // if true, count-up animation
}

export default function MetricCard({ title, value, sub, color = 'var(--cyan)', delay = 0, numeric = false }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    if (!numeric || typeof value !== 'number' || !ref.current) return;
    const el = ref.current;
    const start = performance.now() + delay * 1000;
    const dur = 800;
    const to = value;

    const step = (now: number) => {
      if (now < start) { animRef.current = requestAnimationFrame(step); return; }
      const t = Math.min((now - start) / dur, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(to * ease).toLocaleString();
      if (t < 1) animRef.current = requestAnimationFrame(step);
      else el.textContent = typeof to === 'number' ? to.toLocaleString() : String(to);
    };
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [value, numeric, delay]);

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="metric-title">{title}</div>
      <div
        className="metric-value"
        style={{ color }}
        ref={numeric && typeof value === 'number' ? ref : undefined}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
    </motion.div>
  );
}
