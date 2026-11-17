import React, { useState, useEffect } from 'react';
import { useHealth } from '../hooks/useHealth';

export default function Header({ activeTab, setActiveTab }) {
  const { data: health } = useHealth();
  const [scrollProgress, setScrollProgress] = useState(0);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('lifelane-theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  });

  useEffect(() => {
    const handleScroll = () => {
      const h = document.documentElement;
      const progress = (h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight)) * 100;
      setScrollProgress(progress);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.classList.toggle('dark', nextTheme === 'dark');
    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.style.colorScheme = nextTheme;
    localStorage.setItem('lifelane-theme', nextTheme);
  };

  const navItems = [
    { id: 'home', label: 'Home' },
    { id: 'route', label: 'Route planner' },
    { id: 'system', label: 'System' },
    { id: 'live', label: 'Live demo' },
    { id: 'signals', label: 'Signals & Ops' },
    { id: 'progress', label: 'Progress' },
  ];

  const isOnline = health?.status === 'ok';

  return (
    <>
      {/* Top Gold Scroll Indicator Bar */}
      <div
        id="bar"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          height: '3px',
          width: `${scrollProgress}%`,
          backgroundColor: 'var(--gold)',
          zIndex: 50,
          transition: 'width 0.1s ease-out',
        }}
      />

      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 40,
          backgroundColor: 'var(--g)',
          color: '#ffffff',
          borderBottom: '3px solid var(--gold)',
        }}
      >
        <div className="wrap flex items-center justify-between h-16 gap-3">
          {/* Brand Logo & Name */}
          <button
            onClick={() => setActiveTab('home')}
            className="flex items-center gap-3 text-white text-left focus:outline-none"
            style={{
              fontFamily: '"Bricolage Grotesque", sans-serif',
              fontWeight: 800,
              fontSize: '1.25rem',
            }}
          >
            {/* Pakistan Crescent and Star Emblem */}
            <svg width="36" height="36" viewBox="0 0 60 60" aria-hidden="true" className="flex-shrink-0">
              <circle cx="30" cy="30" r="29" fill="#ffffff" />
              <path d="M33 9a21 21 0 1 0 0 42a16.5 16.5 0 1 1 0-42z" fill="#01411C" />
              <polygon
                points="43,22 45.2,28.4 52,28.4 46.5,32.4 48.6,39 43,35 37.4,39 39.5,32.4 34,28.4 40.8,28.4"
                fill="#01411C"
              />
            </svg>
            <div>
              <span className="leading-tight block">LifeLane</span>
              <small
                className="block text-xs font-normal opacity-80 tracking-wide"
                style={{ fontFamily: '"DM Sans", sans-serif' }}
              >
                Emergency road priority
              </small>
            </div>
          </button>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 overflow-x-auto py-1">
            {navItems.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setActiveTab(item.id);
                    window.location.hash = item.id;
                  }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                    active
                      ? 'bg-white text-[var(--g)] font-bold shadow-sm'
                      : 'text-white/85 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Controls: Backend status + Theme Toggle */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Backend Connectivity Badge */}
            <div
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-black/25 text-white/90 border border-white/15"
              title={isOnline ? 'FastAPI Backend Online (port 8000)' : 'Backend Disconnected (start uvicorn)'}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`}
              />
              <span className="text-[11px]">{isOnline ? 'Engine Online' : 'Simulation Mode'}</span>
            </div>

            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              aria-label="Switch light or dark theme"
              className="px-3 py-1 rounded-full text-xs font-semibold bg-white/15 hover:bg-white/25 text-white transition-colors"
              style={{ fontFamily: '"DM Sans", sans-serif' }}
            >
              {theme === 'dark' ? '?? Light' : '?? Dark'}
            </button>
          </div>
        </div>
      </header>
    </>
  );
}
