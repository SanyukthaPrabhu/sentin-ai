import { useEffect, useRef, useState } from 'react';

interface Point3D {
  x: number;
  y: number;
  z: number;
  baseX: number;
  baseY: number;
  baseZ: number;
  colorType: 'cyan' | 'amber' | 'muted';
  size: number;
}

export default function LandingHeroGlobe() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isLightMode, setIsLightMode] = useState(false);

  // Mouse drag interaction state
  const rotationRef = useRef({ x: 0.5, y: 0.5 });
  const isDragging = useRef(false);
  const previousMousePosition = useRef({ x: 0, y: 0 });

  // Accessibility check
  const prefersReducedMotion = useRef(false);

  useEffect(() => {
    // Check prefers-reduced-motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    prefersReducedMotion.current = mediaQuery.matches;
    const handleMotionChange = (e: MediaQueryListEvent) => {
      prefersReducedMotion.current = e.matches;
    };
    mediaQuery.addEventListener('change', handleMotionChange);

    // Dynamic theme observer
    const observer = new MutationObserver(() => {
      setIsLightMode(document.documentElement.classList.contains('light-mode'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    setIsLightMode(document.documentElement.classList.contains('light-mode'));

    return () => {
      mediaQuery.removeEventListener('change', handleMotionChange);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let width = 0;
    let height = 0;

    // Handle resize
    const resize = () => {
      const container = containerRef.current;
      if (!container) return;
      width = container.clientWidth;
      height = container.clientHeight || 360;
      canvas.width = width * window.devicePixelRatio;
      canvas.height = height * window.devicePixelRatio;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    resize();
    window.addEventListener('resize', resize);

    // Generate globe nodes using Fibonacci Sphere algorithm
    const points: Point3D[] = [];
    const nodeCount = prefersReducedMotion.current ? 40 : 100;
    const radius = 110;

    for (let i = 0; i < nodeCount; i++) {
      const offset = 2 / nodeCount;
      const increment = Math.PI * (3 - Math.sqrt(5)); // Golden angle
      const y = ((i * offset) - 1) + (offset / 2);
      const r = Math.sqrt(1 - y * y);
      const phi = i * increment;
      const x = Math.cos(phi) * r;
      const z = Math.sin(phi) * r;

      // Assign accent colors randomly to match risk indicators
      const rand = Math.random();
      const colorType: 'cyan' | 'amber' | 'muted' = rand > 0.85 ? 'amber' : rand > 0.7 ? 'cyan' : 'muted';
      const size = colorType === 'muted' ? 1.5 : 3;

      points.push({
        x: x * radius,
        y: y * radius,
        z: z * radius,
        baseX: x * radius,
        baseY: y * radius,
        baseZ: z * radius,
        colorType,
        size
      });
    }

    // Satellite state
    let satAngle = 0;
    const satRadiusX = 160;
    const satRadiusZ = 120;

    // Render loop
    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const fov = 350; // Camera distance

      // Dynamic theme colors
      const themeCyan = isLightMode ? '#0284c7' : '#0ea5e9';
      const themeAmber = isLightMode ? '#d97706' : '#f59e0b';
      const themeLine = isLightMode ? 'rgba(15, 23, 42, 0.06)' : 'rgba(248, 250, 252, 0.06)';
      const themeMutedNode = isLightMode ? '#cbd5e1' : '#1e293b';

      // Auto rotation speeds (freeze or slow if reduced motion is requested)
      const rotSpeedY = prefersReducedMotion.current ? 0.0005 : 0.002;
      const rotSpeedX = prefersReducedMotion.current ? 0.0001 : 0.0006;

      if (!isDragging.current) {
        rotationRef.current.y += rotSpeedY;
        rotationRef.current.x += rotSpeedX;
      }

      const cosY = Math.cos(rotationRef.current.y);
      const sinY = Math.sin(rotationRef.current.y);
      const cosX = Math.cos(rotationRef.current.x);
      const sinX = Math.sin(rotationRef.current.x);

      // Rotate nodes and calculate projected coords
      const projected = points.map(pt => {
        // Rotate Y axis
        let x1 = pt.baseX * cosY - pt.baseZ * sinY;
        let z1 = pt.baseX * sinY + pt.baseZ * cosY;

        // Rotate X axis
        let y2 = pt.baseY * cosX - z1 * sinX;
        let z2 = pt.baseY * sinX + z1 * cosX;

        const scale = fov / (fov + z2);
        const px = cx + x1 * scale;
        const py = cy + y2 * scale;

        return {
          px,
          py,
          scale,
          depth: z2, // more negative = closer to camera
          colorType: pt.colorType,
          size: pt.size
        };
      });

      // Project satellite coords
      if (!prefersReducedMotion.current) {
        satAngle += 0.01;
      } else {
        satAngle += 0.002;
      }
      
      const sX = Math.cos(satAngle) * satRadiusX;
      const sY = Math.sin(satAngle) * 30; // tilted orbit
      const sZ = Math.sin(satAngle) * satRadiusZ;

      // Rotate satellite coordinates
      const sX1 = sX * cosY - sZ * sinY;
      const sZ1 = sX * sinY + sZ * cosY;
      const sY2 = sY * cosX - sZ1 * sinX;
      const sZ2 = sY * sinX + sZ1 * cosX;

      const satScale = fov / (fov + sZ2);
      const satPx = cx + sX1 * satScale;
      const satPy = cy + sY2 * satScale;

      // 1. Draw background connections (deep in depth)
      ctx.lineWidth = 0.5;
      for (let i = 0; i < projected.length; i++) {
        const p1 = projected[i];
        if (p1.depth > 0) { // Behind center point
          for (let j = i + 1; j < projected.length; j++) {
            const p2 = projected[j];
            if (p2.depth > 0) {
              const dx = p1.px - p2.px;
              const dy = p1.py - p2.py;
              const dist = Math.sqrt(dx * dx + dy * dy);
              if (dist < 60) {
                ctx.strokeStyle = themeLine;
                ctx.beginPath();
                ctx.moveTo(p1.px, p1.py);
                ctx.lineTo(p2.px, p2.py);
                ctx.stroke();
              }
            }
          }
        }
      }

      // 2. Draw background nodes
      projected.forEach(pt => {
        if (pt.depth > 0) {
          ctx.beginPath();
          ctx.arc(pt.px, pt.py, pt.size * pt.scale * 0.7, 0, Math.PI * 2);
          ctx.fillStyle = pt.colorType === 'cyan' ? themeCyan : pt.colorType === 'amber' ? themeAmber : themeMutedNode;
          ctx.fill();
        }
      });

      // 3. Draw orbit line for satellite (back section)
      ctx.strokeStyle = isLightMode ? 'rgba(15, 23, 42, 0.04)' : 'rgba(248, 250, 252, 0.04)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      // Draw satellite path as ellipse
      ctx.ellipse(cx, cy, satRadiusX * 0.9, 35, rotationRef.current.x, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // 4. Draw foreground connections (close to camera)
      for (let i = 0; i < projected.length; i++) {
        const p1 = projected[i];
        if (p1.depth <= 0) {
          for (let j = i + 1; j < projected.length; j++) {
            const p2 = projected[j];
            const dx = p1.px - p2.px;
            const dy = p1.py - p2.py;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 65) {
              ctx.strokeStyle = p1.depth <= 0 && p2.depth <= 0 
                ? (isLightMode ? 'rgba(15, 23, 42, 0.09)' : 'rgba(248, 250, 252, 0.09)') 
                : themeLine;
              ctx.beginPath();
              ctx.moveTo(p1.px, p1.py);
              ctx.lineTo(p2.px, p2.py);
              ctx.stroke();
            }
          }
        }
      }

      // 5. Draw foreground nodes with glowing effects
      projected.forEach(pt => {
        if (pt.depth <= 0) {
          ctx.beginPath();
          ctx.arc(pt.px, pt.py, pt.size * pt.scale, 0, Math.PI * 2);
          if (pt.colorType === 'cyan') {
            ctx.fillStyle = themeCyan;
            ctx.shadowColor = themeCyan;
            ctx.shadowBlur = 8;
          } else if (pt.colorType === 'amber') {
            ctx.fillStyle = themeAmber;
            ctx.shadowColor = themeAmber;
            ctx.shadowBlur = 8;
          } else {
            ctx.fillStyle = isLightMode ? '#94a3b8' : '#475569';
            ctx.shadowBlur = 0;
          }
          ctx.fill();
          ctx.shadowBlur = 0; // reset
        }
      });

      // 6. Draw Satellite and its beam connector
      if (sZ2 < 0) { // Satellite is in the foreground
        // Beam to center of the globe
        ctx.strokeStyle = isLightMode ? 'rgba(2, 132, 199, 0.15)' : 'rgba(14, 165, 233, 0.15)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 4]);
        ctx.beginPath();
        ctx.moveTo(satPx, satPy);
        ctx.lineTo(cx, cy);
        ctx.stroke();
        ctx.setLineDash([]);

        // Outer glow
        ctx.beginPath();
        ctx.arc(satPx, satPy, 6 * satScale, 0, Math.PI * 2);
        ctx.fillStyle = isLightMode ? 'rgba(2, 132, 199, 0.2)' : 'rgba(14, 165, 233, 0.2)';
        ctx.fill();

        // Core satellite
        ctx.beginPath();
        ctx.arc(satPx, satPy, 3 * satScale, 0, Math.PI * 2);
        ctx.fillStyle = themeCyan;
        ctx.shadowColor = themeCyan;
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Draw small satellite panels
        ctx.fillStyle = isLightMode ? '#334155' : '#cbd5e1';
        ctx.fillRect(satPx - 8 * satScale, satPy - 1 * satScale, 4 * satScale, 2 * satScale);
        ctx.fillRect(satPx + 4 * satScale, satPy - 1 * satScale, 4 * satScale, 2 * satScale);
      }

      animationId = requestAnimationFrame(render);
    };

    render();

    // Mouse drag handlers
    const handleMouseDown = (e: MouseEvent) => {
      isDragging.current = true;
      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const deltaX = e.clientX - previousMousePosition.current.x;
      const deltaY = e.clientY - previousMousePosition.current.y;
      
      rotationRef.current.y += deltaX * 0.005;
      rotationRef.current.x += deltaY * 0.005;

      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseUp = () => {
      isDragging.current = false;
    };

    // Touch support
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 0) return;
      isDragging.current = true;
      previousMousePosition.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging.current || e.touches.length === 0) return;
      const deltaX = e.touches[0].clientX - previousMousePosition.current.x;
      const deltaY = e.touches[0].clientY - previousMousePosition.current.y;

      rotationRef.current.y += deltaX * 0.005;
      rotationRef.current.x += deltaY * 0.005;

      previousMousePosition.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    };

    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    canvas.addEventListener('touchstart', handleTouchStart);
    window.addEventListener('touchmove', handleTouchMove);
    window.addEventListener('touchend', handleMouseUp);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);

      canvas.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleMouseUp);
    };
  }, [isLightMode]);

  return (
    <div 
      ref={containerRef} 
      style={{ 
        width: '100%', 
        height: '360px', 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center',
        position: 'relative',
        cursor: isDragging.current ? 'grabbing' : 'grab'
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block', maxWidth: '100%' }} />
    </div>
  );
}
