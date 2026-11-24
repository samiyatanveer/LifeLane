// EventLog.tsx
import { useEffect, useRef } from 'react';
import type { SimEvent } from '../types';

interface Props { events: SimEvent[]; t0?: number; }

const CLS_MAP: Record<string, string> = { ok:'log-g', warn:'log-a', info:'log-b', error:'log-r' };

export default function EventLog({ events, t0 = 0 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <div className="card">
      <h3>Event log</h3>
      <div id="log-container" ref={containerRef}>
        {events.map((e, i) => (
          <div
            key={i}
            className={`log-entry ${CLS_MAP[e.level] ?? ''}`}
          >
            {String(Math.max(0, e.t - t0).toFixed(1)).padStart(5)}s&nbsp;&nbsp;{e.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
