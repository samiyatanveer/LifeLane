export default function Footer() {
  return (
    <footer className="bg-[#032b1c] text-emerald-50 mt-auto border-t border-emerald-900/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-9">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h3 className="font-bold text-white text-lg mb-2">LifeLane</h3>
            <p className="text-sm text-emerald-200/70">
              Intelligent Ambulance Signal Priority System for coordinated emergency mobility.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-2">Simulation Environment</h4>
            <p className="text-sm text-emerald-200/70 leading-relaxed">
              Traffic signals and dispatch operations are simulated using SUMO. This demonstration is not connected to live traffic infrastructure.
            </p>
          </div>
        </div>
        <div className="border-t border-emerald-800 mt-7 pt-5 text-center text-xs text-emerald-400">
          Simulation Environment: Traffic signals and dispatch operations are simulated using SUMO. This demonstration is not connected to live traffic infrastructure.
        </div>
      </div>
    </footer>
  );
}
