import { Link, useLocation } from 'react-router-dom';
import { X, Home, Mic, TrafficCone, Clock, ArrowLeft, Ambulance } from 'lucide-react';
import SimulationBadge from '../ui/SimulationBadge';
import ThemeToggle from '../ui/ThemeToggle';

const NAV_ITEMS = [
  { label: 'Dashboard', icon: Home, to: '/dashboard' },
  { label: 'Detection', icon: Mic, to: '/detection' },
  { label: 'Signals', icon: TrafficCone, to: '/signals' },
  { label: 'History', icon: Clock, to: '/history' },
];

function NavItem({ item, active, onClick }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      onClick={onClick}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
        ${active
          ? 'bg-gradient-to-r from-[#063d2b] to-[#087f5b] text-white shadow-md shadow-emerald-900/15'
          : 'text-gray-600 hover:bg-green-50 hover:text-[#087f5b]'
        }`}
    >
      <Icon className="w-5 h-5 flex-shrink-0" />
      {item.label}
    </Link>
  );
}

export function SidebarContent({ onClose }) {
  const location = useLocation();

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center justify-between p-5 border-b border-gray-200">
        <Link to="/dashboard" className="flex items-center gap-3 font-bold text-slate-900 text-lg" onClick={onClose}>
          <span className="grid place-items-center w-9 h-9 rounded-xl bg-gradient-to-br from-[#087f5b] to-[#063d2b] text-white shadow-lg shadow-emerald-900/25"><Ambulance className="w-5 h-5" /></span>
          <span>Life<span className="text-[#087f5b]">Lane</span></span>
        </Link>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-md hover:bg-gray-100 lg:hidden">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        )}
      </div>

      {/* Simulation badge */}
      <div className="px-4 py-4">
        <SimulationBadge className="w-full justify-center" />
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.to}
            item={item}
            active={location.pathname === item.to}
            onClick={onClose}
          />
        ))}
      </nav>

      {/* Back to home */}
      <div className="px-3 py-4 border-t border-gray-200 space-y-2">
        <ThemeToggle className="w-full justify-center" />
        <Link
          to="/"
          onClick={onClose}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Home
        </Link>
      </div>
    </div>
  );
}

export default function Sidebar({ mobileOpen, onClose }) {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="sidebar-surface hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 lg:border-r lg:border-gray-200 z-30 shadow-[8px_0_30px_rgba(6,61,43,.03)]">
        <SidebarContent />
      </aside>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div
            className="fixed inset-0 bg-black/40"
            onClick={onClose}
            aria-hidden="true"
          />
          <div className="sidebar-surface relative flex flex-col w-72 max-w-xs shadow-xl">
            <SidebarContent onClose={onClose} />
          </div>
        </div>
      )}
    </>
  );
}
