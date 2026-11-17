import React from 'react';

export default function ProgressOverview() {
  const timeline = [
    {
      title: 'Mock proof of concept',
      status: 'Done',
      statusClass: 'bg-[var(--tint)] text-[var(--g2)]',
      desc: 'Route planning, 3-window siren confirmation, emergency authorization, signal priority state machine, expiry and conflict checks, GPS deviation detection, and bounded recovery all pass across 286 automated tests.',
    },
    {
      title: 'FastAPI Backend & React Frontend',
      status: 'Built',
      statusClass: 'bg-[var(--tint)] text-[var(--g2)]',
      desc: 'Complete asynchronous REST architecture with detection, dispatch, health, and signals modules, paired with responsive React UI, Tailwind design system, and SQLite database.',
    },
    {
      title: 'Siren Model on Real Karachi Dataset',
      status: 'Integrated',
      statusClass: 'bg-[var(--tint)] text-[var(--g2)]',
      desc: 'YAMNet acoustic feature extraction pipeline configured for the Karachi Emergency Siren dataset, with MockYAMNet fallback for offline execution.',
    },
    {
      title: 'Full SUMO Simulation & TraCI Integration',
      status: 'Next Step',
      statusClass: 'bg-amber-100 text-amber-800',
      desc: 'Eclipse SUMO network XML (2x2 grid) configured. Runs seamlessly via MockSumoRunner when SUMO is not locally installed on the host OS.',
    },
  ];

  const chips = [
    'Python 3.14',
    'FastAPI',
    'React 19',
    'Tailwind CSS',
    'Vite',
    'XGBoost',
    'Pytest (286 Tests)',
    'SQLite & aiosqlite',
    'SQLAlchemy 2.0',
    'Google YAMNet',
    'Git & GitHub',
  ];

  return (
    <section className="py-12 wrap">
      <h2>Where the project stands</h2>
      <p className="mt-2 mb-8">
        LifeLane is developed in disciplined, verified milestones adhering strictly to the FYP Project Specification.
      </p>

      {/* Timeline */}
      <div className="border-l-2 border-[var(--line)] pl-6 space-y-8 ml-2">
        {timeline.map((item) => (
          <div key={item.title} className="relative">
            {/* Dot marker */}
            <span
              className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full border-2 border-[var(--bg)]"
              style={{ backgroundColor: item.status === 'Next Step' ? 'var(--gold)' : 'var(--g2)' }}
            />
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-[var(--ink)]">{item.title}</h3>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${item.statusClass}`}>
                {item.status}
              </span>
            </div>
            <p className="text-sm mt-1 text-[var(--mute)] leading-relaxed max-w-[62ch]">
              {item.desc}
            </p>
          </div>
        ))}
      </div>

      <h2 className="mt-14 mb-2">Built with</h2>
      <p className="mb-4">Industry-standard, CPU-friendly technologies chosen for reproducible deployment.</p>

      {/* Tech Chips */}
      <div className="flex flex-wrap gap-2.5">
        {chips.map((chip) => (
          <span
            key={chip}
            className="px-3.5 py-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] text-xs font-semibold text-[var(--ink)] shadow-sm"
          >
            {chip}
          </span>
        ))}
      </div>
    </section>
  );
}
