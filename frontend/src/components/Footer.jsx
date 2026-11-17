import React from 'react';

export default function Footer() {
  return (
    <footer
      className="mt-16 py-8"
      style={{
        backgroundColor: 'var(--g)',
        color: '#ffffff',
        borderTop: '3px solid var(--gold)',
      }}
    >
      <div className="wrap flex flex-col sm:flex-row items-center justify-between gap-4 text-xs opacity-90">
        <p className="text-white text-xs m-0">
          <strong>LifeLane</strong>: emergency road priority for Pakistan. Educational final year project prototype.
        </p>
        <p className="text-white text-xs m-0 text-center sm:text-right opacity-80">
          Simulation and research only. Never connect directly to live municipal road signals.
        </p>
      </div>
    </footer>
  );
}
