import { Link } from 'react-router-dom';
import { useState } from 'react';
import { Menu, X, Ambulance } from 'lucide-react';
import SimulationBadge from '../ui/SimulationBadge';

const NAV_LINKS = [
  { label: 'About', href: '#about' },
  { label: 'Features', href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 font-bold text-[#087F5B] text-xl">
            <Ambulance className="w-7 h-7" />
            LifeLane
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-600">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="hover:text-[#087F5B] transition-colors"
              >
                {l.label}
              </a>
            ))}
            <SimulationBadge />
            <Link
              to="/dashboard"
              className="ml-2 px-4 py-2 rounded-lg bg-[#087F5B] text-white text-sm font-medium hover:bg-[#0B5D3B] transition-colors"
            >
              Open Dashboard
            </Link>
          </nav>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-md text-gray-600 hover:text-[#087F5B]"
            onClick={() => setOpen(!open)}
            aria-label="Toggle menu"
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-gray-200 bg-white px-4 py-4 space-y-3">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="block text-sm font-medium text-gray-600 hover:text-[#087F5B]"
              onClick={() => setOpen(false)}
            >
              {l.label}
            </a>
          ))}
          <SimulationBadge />
          <Link
            to="/dashboard"
            className="block mt-2 px-4 py-2 rounded-lg bg-[#087F5B] text-white text-sm font-medium text-center"
            onClick={() => setOpen(false)}
          >
            Open Dashboard
          </Link>
        </div>
      )}
    </header>
  );
}
