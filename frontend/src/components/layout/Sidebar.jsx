import { Link, useLocation } from 'react-router-dom';
import { X, Home, Mic, TrafficCone, Clock, ArrowLeft, Ambulance } from 'lucide-react';
import SimulationBadge from '../ui/SimulationBadge';

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
          ? 'bg-[#087F5B] text-white'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
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
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <Link to="/dashboard" className="flex items-center gap-2 font-bold text-[#087F5B] text-lg" onClick={onClose}>
          <Ambulance className="w-6 h-6" />
          LifeLane
        </Link>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-md hover:bg-gray-100 lg:hidden">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        )}
      </div>

      {/* Simulation badge */}
      <div className="px-4 py-3">
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
      <div className="px-3 py-4 border-t border-gray-200">
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
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 lg:border-r lg:border-gray-200 lg:bg-white z-30">
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
          <div className="relative flex flex-col w-72 max-w-xs bg-white shadow-xl">
            <SidebarContent onClose={onClose} />
          </div>
        </div>
      )}
    </>
  );
}
