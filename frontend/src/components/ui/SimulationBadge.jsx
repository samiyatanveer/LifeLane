export default function SimulationBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold tracking-widest
        bg-red-50 text-red-700 border-2 border-red-400 uppercase ${className}`}
      title="This is a simulation only. No real traffic infrastructure is connected."
    >
      ⚠ SIMULATION
    </span>
  );
}
