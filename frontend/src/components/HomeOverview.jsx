import React from 'react';
import HeroStage from './HeroStage';

export default function HomeOverview({ onNavigate }) {
  return (
    <div>
      {/* Hero Section with Road Stage Simulation */}
      <HeroStage
        onNavigateToRoute={() => onNavigate('route')}
        onNavigateToSystem={() => onNavigate('system')}
      />

      {/* What LifeLane Does in Plain Words */}
      <section className="py-14 wrap">
        <h2>What LifeLane does, in plain words</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-8">
          <div className="p-6 rounded-2xl bg-[var(--tint)] border border-[var(--line)]">
            <b className="block text-lg font-bold mb-2 text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              The problem
            </b>
            <p className="text-sm leading-relaxed text-[var(--ink)]">
              Ambulances get trapped at congested signalized intersections and gridlocked corridors, causing critical delays when every minute directly impacts patient survival.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[var(--tint)] border border-[var(--line)]">
            <b className="block text-lg font-bold mb-2 text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              Our solution
            </b>
            <p className="text-sm leading-relaxed text-[var(--ink)]">
              Acoustic roadside sensing identifies the siren; the central engine confirms ambulance authorization, plans the fastest hospital route, and clears traffic lights just in time.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[var(--tint)] border border-[var(--line)]">
            <b className="block text-lg font-bold mb-2 text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              The result
            </b>
            <p className="text-sm leading-relaxed text-[var(--ink)]">
              An uninterrupted, collision-free transit wave to the hospital, followed by automated bounded recovery that smoothly restores normal coordinated traffic timing.
            </p>
          </div>
        </div>

        {/* Explore the Project Cards */}
        <h2 className="mt-16 mb-2">Explore the project</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-6">
          <button
            onClick={() => onNavigate('system')}
            className="life-card text-left cursor-pointer group"
          >
            <h3>How it works</h3>
            <p className="text-sm mt-2">
              The four steps from a heard siren to a recovered road, and the decoupled Python modules behind them.
            </p>
            <em className="inline-block mt-4 text-xs font-bold text-[var(--g2)] not-italic group-hover:underline">
              Open the system page &rarr;
            </em>
          </button>

          <button
            onClick={() => onNavigate('live')}
            className="life-card text-left cursor-pointer group"
          >
            <h3>Live demo</h3>
            <p className="text-sm mt-2">
              Run the 12 simulation test scenarios, explore acoustic harmonic frequency bins, or run live inference.
            </p>
            <em className="inline-block mt-4 text-xs font-bold text-[var(--g2)] not-italic group-hover:underline">
              Open the live demo &rarr;
            </em>
          </button>

          <button
            onClick={() => onNavigate('signals')}
            className="life-card text-left cursor-pointer group"
          >
            <h3>Signals & Operations</h3>
            <p className="text-sm mt-2">
              Interact with the 4-junction preemption state machine (J1–J4), trigger green priority, and view live audit logs.
            </p>
            <em className="inline-block mt-4 text-xs font-bold text-[var(--g2)] not-italic group-hover:underline">
              Open signal controller &rarr;
            </em>
          </button>
        </div>

        {/* Quick Facts Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-14 pt-8 border-t border-[var(--line)]">
          <div className="border-l-4 border-[var(--gold)] pl-4">
            <b className="block text-3xl font-black text-[var(--g2)] leading-none" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              12 / 12
            </b>
            <small className="text-xs text-[var(--mute)] font-medium mt-1 block">
              Core simulation scenarios verified passing
            </small>
          </div>

          <div className="border-l-4 border-[var(--gold)] pl-4">
            <b className="block text-3xl font-black text-[var(--g2)] leading-none" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              1,800
            </b>
            <small className="text-xs text-[var(--mute)] font-medium mt-1 block">
              Karachi siren and traffic sound clips for training
            </small>
          </div>

          <div className="border-l-4 border-[var(--gold)] pl-4">
            <b className="block text-3xl font-black text-[var(--g2)] leading-none" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              4 Modules
            </b>
            <small className="text-xs text-[var(--mute)] font-medium mt-1 block">
              FastAPI architecture: detection, dispatch, signals, health
            </small>
          </div>
        </div>
      </section>
    </div>
  );
}
