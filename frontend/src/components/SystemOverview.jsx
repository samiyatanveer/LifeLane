import React from 'react';

export default function SystemOverview() {
  const steps = [
    {
      num: 1,
      title: 'Siren heard',
      desc: 'Directional roadside microphones pick up ambient audio on all 4 intersection approaches. Deep learning feature extraction (Google YAMNet) and Logistic Regression confirm an authentic emergency siren with 3 consecutive verification windows.',
    },
    {
      num: 2,
      title: 'Request verified',
      desc: 'Siren sound alone NEVER triggers a green signal. The system verifies identity via registered onboard hardware or dispatcher emergency tokens, ensuring the request is valid, authorized, and non-expired.',
    },
    {
      num: 3,
      title: 'Signals cleared',
      desc: 'Dynamic Dijkstra routing calculates the optimal path. The independent Safety Controller clears conflicting traffic with a mandatory 3s yellow and 2s all-red phase before activating green priority for the ambulance approach.',
    },
    {
      num: 4,
      title: 'Traffic recovers',
      desc: 'Loop detectors or exit coordinates confirm vehicle passage (never audio silence). The controller enters bounded recovery, compensating delayed cross-traffic and smoothly realigning coordinated grid cycles.',
    },
  ];

  const modules = [
    {
      name: 'Detection Engine',
      tag: 'Acoustic ML',
      desc: '1024-dim YAMNet embeddings with scikit-learn binary classifier trained on the Karachi Emergency Siren dataset.',
    },
    {
      name: 'Dispatch & Registry',
      tag: 'Identity & Auth',
      desc: 'Tracks ambulance registration, temporary verification pathways, and Dijkstra / A* route planning.',
    },
    {
      name: 'Safety Controller',
      tag: 'Signal Preemption',
      desc: 'Enforces non-negotiable safety guardrails, yellow/all-red clearances, and bounded corridor recovery.',
    },
    {
      name: 'FastAPI Health & Telemetry',
      tag: 'Core REST API',
      desc: 'High-speed asynchronous endpoints for real-time traffic monitoring, audit logging, and Swagger docs.',
    },
  ];

  return (
    <section className="py-12 wrap">
      <h2>From siren to cleared road in four steps</h2>
      <p className="mt-2 mb-8">
        LifeLane bridges acoustic sensing, cryptographic dispatch verification, and safety-constrained traffic control into one coordinated pipeline.
      </p>

      {/* 4 Step Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {steps.map((st) => (
          <div
            key={st.num}
            className="life-card flex gap-4 items-start"
            style={{ borderTopColor: 'var(--g2)' }}
          >
            <span
              className="flex-shrink-0 w-11 h-11 rounded-full grid place-items-center text-white font-extrabold text-lg"
              style={{ backgroundColor: 'var(--g)', fontFamily: '"Bricolage Grotesque", sans-serif' }}
            >
              {st.num}
            </span>
            <div>
              <h3>{st.title}</h3>
              <p className="mt-1 text-sm leading-relaxed">{st.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <h2 className="mt-14 mb-2">What runs behind it</h2>
      <p className="mb-6">Four decoupled modules keep domain logic, machine learning, and traffic safety separated.</p>

      {/* Architecture Modules Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {modules.map((m) => (
          <div key={m.name} className="life-card p-5" style={{ borderTopColor: 'var(--gold)' }}>
            <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-[var(--gold)] mb-1">
              {m.tag}
            </span>
            <h3 className="text-base font-bold text-[var(--ink)] mb-2">{m.name}</h3>
            <p className="text-xs leading-relaxed">{m.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
