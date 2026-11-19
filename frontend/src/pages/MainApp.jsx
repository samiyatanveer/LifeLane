import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import HomeOverview from '../components/HomeOverview';
import RoutePlanner from '../components/RoutePlanner';
import SystemOverview from '../components/SystemOverview';
import LiveDemo from '../components/LiveDemo';
import SignalsOps from '../components/SignalsOps';
import Footer from '../components/Footer';

export default function MainApp({ defaultTab = 'home' }) {
  const [activeTab, setActiveTab] = useState(() => {
    const hash = window.location.hash.replace('#', '');
    const validTabs = ['home', 'route', 'system', 'live', 'signals'];
    return validTabs.includes(hash) ? hash : defaultTab;
  });

  // Keep hash in sync
  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      const validTabs = ['home', 'route', 'system', 'live', 'signals'];
      if (validTabs.includes(hash)) {
        setActiveTab(hash);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    window.location.hash = tabId;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen flex flex-col justify-between" style={{ backgroundColor: 'var(--bg)', color: 'var(--ink)' }}>
      <div>
        <Header activeTab={activeTab} setActiveTab={handleTabChange} />

        <main className="page-anim">
          {activeTab === 'home' && <HomeOverview onNavigate={handleTabChange} />}
          {activeTab === 'route' && <RoutePlanner />}
          {activeTab === 'system' && <SystemOverview />}
          {activeTab === 'live' && <LiveDemo />}
          {activeTab === 'signals' && <SignalsOps />}
        </main>
      </div>

      <Footer />
    </div>
  );
}
