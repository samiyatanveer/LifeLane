import { Link } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { Mic, Shield, TrafficCone, Zap, Map, AlertTriangle, Radio, ArrowRight, ChevronDown } from 'lucide-react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';

function FadeUp({ children, delay = 0 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 32 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  );
}

function AmbulanceAnimation() {
  return (
    <div className="relative w-full max-w-sm mx-auto h-64 select-none" aria-hidden="true">
      <svg viewBox="0 0 320 260" className="w-full h-full" fill="none">
        {/* Road grid */}
        <rect x="130" y="0" width="60" height="260" rx="0" fill="#e5e7eb" />
        <rect x="0" y="100" width="320" height="60" rx="0" fill="#e5e7eb" />
        {/* Junction center */}
        <rect x="130" y="100" width="60" height="60" fill="#d1d5db" />
        {/* Road markings */}
        <line x1="160" y1="10" x2="160" y2="90" stroke="white" strokeWidth="3" strokeDasharray="12 8" />
        <line x1="160" y1="170" x2="160" y2="250" stroke="white" strokeWidth="3" strokeDasharray="12 8" />
        <line x1="10" y1="130" x2="120" y2="130" stroke="white" strokeWidth="3" strokeDasharray="12 8" />
        <line x1="200" y1="130" x2="310" y2="130" stroke="white" strokeWidth="3" strokeDasharray="12 8" />
        {/* Signal lights */}
        <circle cx="125" cy="95" r="8" fill="#16a34a" />
        <circle cx="195" cy="165" r="8" fill="#16a34a" />
        <circle cx="195" cy="95" r="8" fill="#dc2626" />
        <circle cx="125" cy="165" r="8" fill="#dc2626" />
        {/* Animated ambulance */}
        <g style={{ animation: 'ambulanceMove 3s ease-in-out infinite' }}>
          <rect x="145" y="230" width="30" height="18" rx="3" fill="white" stroke="#087F5B" strokeWidth="2" />
          <rect x="145" y="230" width="30" height="18" rx="3" fill="#087F5B" fillOpacity="0.15" />
          <line x1="160" y1="232" x2="160" y2="246" stroke="#087F5B" strokeWidth="2" />
          <line x1="153" y1="239" x2="167" y2="239" stroke="#087F5B" strokeWidth="2" />
          <circle cx="150" cy="249" r="3" fill="#374151" />
          <circle cx="170" cy="249" r="3" fill="#374151" />
          {/* Siren flash */}
          <rect x="148" y="228" width="6" height="4" rx="1" fill="#ef4444" style={{ animation: 'sirenFlash 0.5s ease-in-out infinite alternate' }} />
          <rect x="166" y="228" width="6" height="4" rx="1" fill="#3b82f6" style={{ animation: 'sirenFlash 0.5s ease-in-out infinite alternate-reverse' }} />
        </g>
      </svg>
      <style>{`
        @keyframes ambulanceMove {
          0% { transform: translateY(0px); }
          50% { transform: translateY(-160px); }
          100% { transform: translateY(0px); }
        }
        @keyframes sirenFlash {
          from { opacity: 1; }
          to { opacity: 0.2; }
        }
        @media (prefers-reduced-motion: reduce) {
          @keyframes ambulanceMove { 0%, 100% { transform: none; } }
          @keyframes sirenFlash { from { opacity: 1; } to { opacity: 1; } }
        }
      `}</style>
    </div>
  );
}

const STEPS = [
  {
    icon: Mic,
    title: 'Audio Detection',
    desc: 'Siren sound is detected on an approach using YAMNet ML embeddings + Logistic Regression. Confidence threshold enforced.',
  },
  {
    icon: Shield,
    title: 'Identity Verification',
    desc: 'Ambulance identity is verified through the LifeLane registry or temporary operator confirmation. Fake claims are rejected.',
  },
  {
    icon: TrafficCone,
    title: 'Signal Priority',
    desc: 'Only after full three-tier authorization does the SUMO simulation grant a safe green signal to the verified ambulance.',
  },
];

const FEATURES = [
  { icon: Mic, title: 'Audio ML Detection', tag: 'Intelligence Layer', desc: 'YAMNet embeddings classify siren audio with a trained Logistic Regression model.' },
  { icon: Map, title: 'Route Planning', tag: 'Simulation Environment', desc: 'Emergency routes computed within the SUMO traffic simulation environment.' },
  { icon: TrafficCone, title: 'Signal Safety', tag: '(Simulated)', desc: 'Signal state machine with bounded recovery — SERVING times out automatically.' },
  { icon: Shield, title: 'Three-Tier Verification', tag: 'Safety Workflow', desc: 'Audio → Identity → Request approval before any priority is granted.' },
  { icon: Zap, title: 'Bounded Recovery', tag: '(Simulated)', desc: 'All signal changes are time-bounded. No junction can stay in SERVING indefinitely.' },
  { icon: Radio, title: 'SUMO Simulation', tag: 'Simulation Environment', desc: 'Industry-standard SUMO traffic simulator models intersection behaviour.' },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#F6F8F7] flex flex-col">
      <Navbar />

      {/* Hero */}
      <section className="relative bg-gradient-to-br from-[#032b1c] via-[#075b43] to-[#087f5b] text-white overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_30%_50%,rgba(255,255,255,0.4),transparent)]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-green-200 text-sm font-medium mb-6 border border-white/20">
                Simulation Environment
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
                LifeLane
                <span className="block text-emerald-200 text-3xl sm:text-4xl mt-1">
                  Intelligent Ambulance Signal Priority System
                </span>
              </h1>
              <p className="text-lg text-slate-100 mb-4 max-w-xl">
                A smart, route-aware emergency mobility platform designed to improve ambulance movement through coordinated traffic signal prioritization.
              </p>
              <p className="text-sm text-slate-300 mb-8 max-w-xl">
                Simulation Environment: Traffic signals and dispatch operations are simulated using SUMO. This demonstration is not connected to live traffic infrastructure.
              </p>
              <div className="flex flex-wrap gap-4">
                <Link
                  to="/dashboard"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-[#087f5b] font-semibold hover:bg-emerald-50 transition-colors shadow-lg"
                >
                  Open Operations Dashboard <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white/10 text-white font-medium border border-white/30 hover:bg-white/20 transition-colors"
                >
                  Learn How It Works <ChevronDown className="w-4 h-4" />
                </a>
              </div>
            </div>
            <div className="hidden lg:block">
              <AmbulanceAnimation />
            </div>
          </div>
        </div>
      </section>

      {/* Safety notice */}
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-3 text-amber-800 text-sm font-medium">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-600" />
          Simulation Environment: Traffic signals and dispatch operations are simulated using SUMO. This demonstration is not connected to live traffic infrastructure.
        </div>
      </div>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <FadeUp>
          <div className="text-center mb-12">
            <span className="text-sm font-semibold text-[#087f5b] uppercase tracking-widest">Process</span>
            <h2 className="mt-2 text-3xl font-extrabold text-gray-900">How It Works</h2>
            <p className="mt-3 text-gray-500 max-w-2xl mx-auto">
              Three independent verification steps must all succeed before any signal is changed. No shortcut bypasses this chain.
            </p>
          </div>
        </FadeUp>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <FadeUp key={step.title} delay={i * 0.15}>
                <div className="relative bg-white rounded-2xl border border-gray-200 shadow-sm p-8 text-center hover:shadow-md transition-shadow">
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-[#087f5b] text-white flex items-center justify-center font-bold text-sm shadow">
                    {i + 1}
                  </div>
                  <div className="flex justify-center mb-4 mt-2">
                    <div className="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center">
                      <Icon className="w-7 h-7 text-[#087f5b]" />
                    </div>
                  </div>
                  <h3 className="font-bold text-gray-900 text-lg mb-2">{step.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{step.desc}</p>
                </div>
              </FadeUp>
            );
          })}
        </div>
      </section>

      {/* Architecture */}
      <section id="about" className="bg-white py-20">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <FadeUp>
            <div className="text-center mb-12">
            <span className="text-sm font-semibold text-[#087f5b] uppercase tracking-widest">System Design</span>
              <h2 className="mt-2 text-3xl font-extrabold text-gray-900">System Architecture</h2>
              <p className="mt-3 text-gray-500">Three-tier verification flow — all within a single simulated environment.</p>
            </div>
          </FadeUp>
          <FadeUp delay={0.1}>
            <div className="flex flex-col md:flex-row items-center justify-center gap-0 md:gap-0">
              {[
                { label: 'Audio Layer', sub: 'YAMNet + LR', color: 'bg-[#087f5b]' },
                { label: 'Identity Layer', sub: 'Registry check', color: 'bg-[#075b43]' },
                { label: 'Authorization Layer', sub: 'Request approval', color: 'bg-[#063d2b]' },
                { label: 'Signal Control', sub: 'SUMO simulation', color: 'bg-gray-800' },
              ].map((tier, i, arr) => (
                <div key={tier.label} className="flex flex-col md:flex-row items-center">
                  <div className={`${tier.color} text-white px-6 py-4 rounded-xl shadow text-center min-w-[140px]`}>
                    <div className="font-bold text-sm">{tier.label}</div>
                    <div className="text-xs text-white/70 mt-0.5">{tier.sub}</div>
                  </div>
                  {i < arr.length - 1 && (
                    <div className="text-gray-400 text-2xl font-light mx-3 my-2 md:my-0">→</div>
                  )}
                </div>
              ))}
            </div>
            <p className="text-center text-xs text-gray-400 mt-6">
              Each arrow represents a gate that must pass. Failure at any tier stops the process.
            </p>
          </FadeUp>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <FadeUp>
          <div className="text-center mb-12">
            <span className="text-sm font-semibold text-[#087f5b] uppercase tracking-widest">Capabilities</span>
            <h2 className="mt-2 text-3xl font-extrabold text-gray-900">System Features</h2>
            <p className="mt-3 text-gray-500 max-w-2xl mx-auto">
              LifeLane is presented within a controlled SUMO simulation environment and is not connected to live traffic infrastructure.
            </p>
          </div>
        </FadeUp>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <FadeUp key={f.title} delay={i * 0.08}>
                <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow h-full">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-[#087f5b]" />
                    </div>
                    <div>
                      <span className="font-semibold text-gray-900 text-sm block">{f.title}</span>
                      <span className="text-xs text-amber-600 font-medium">{f.tag}</span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
                </div>
              </FadeUp>
            );
          })}
        </div>
      </section>

      <Footer />
    </div>
  );
}
