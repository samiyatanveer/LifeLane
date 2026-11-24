// MapCanvas.tsx – renders the static city + dynamic animation
import { useEffect, useRef } from 'react';
import { buildStatic, render, type Camera } from '../renderer';
import type { Snapshot } from '../types';

interface Props {
  snapshot: Snapshot;
  cam: Camera;
  follow: boolean;
}

export default function MapCanvas({ snapshot, cam, follow }: Props) {
  const cvRef = useRef<HTMLCanvasElement>(null);
  const staticRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef(0);
  const snapRef = useRef(snapshot);
  const camRef = useRef(cam);

  // Update refs every render without restarting the loop
  snapRef.current = snapshot;
  camRef.current = cam;
  camRef.current.follow = follow;

  useEffect(() => {
    staticRef.current = buildStatic();
  }, []);

  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;

    function resize() {
      const b = cv!.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      cv!.width = Math.round(b.width * dpr);
      cv!.height = Math.round(b.height * dpr);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv);

    function loop(now: number) {
      const ctx = cv!.getContext('2d');
      if (!ctx || !staticRef.current) { rafRef.current = requestAnimationFrame(loop); return; }
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      render(snapRef.current, now, camRef.current, staticRef.current, cv!, ctx, dpr);
      rafRef.current = requestAnimationFrame(loop);
    }
    rafRef.current = requestAnimationFrame(loop);

    return () => { cancelAnimationFrame(rafRef.current); ro.disconnect(); };
  }, []);

  return (
    <canvas
      ref={cvRef}
      style={{ display:'block', width:'100%', height:'100%' }}
    />
  );
}
