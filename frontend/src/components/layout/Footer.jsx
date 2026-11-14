export default function Footer() {
  return (
    <footer className="bg-[#063D2B] text-green-100 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="font-bold text-white text-lg mb-2">LifeLane</h3>
            <p className="text-sm text-green-200">
              Smart Ambulance Signal Priority — Final Year Project (FYP) simulation system.
              Not for real traffic control use.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-2">Tech Stack</h4>
            <ul className="text-sm text-green-200 space-y-1">
              <li>React + Vite + Tailwind CSS</li>
              <li>FastAPI + SQLAlchemy (backend)</li>
              <li>YAMNet + Scikit-learn (ML)</li>
              <li>SUMO Traffic Simulation</li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-2">Context</h4>
            <ul className="text-sm text-green-200 space-y-1">
              <li>Academic Final Year Project</li>
              <li>Proof-of-concept simulation only</li>
              <li>Not connected to real infrastructure</li>
            </ul>
          </div>
        </div>
        <div className="border-t border-green-800 mt-8 pt-6 text-center text-xs text-green-400">
          ⚠ LifeLane is an educational simulation. It never connects to real traffic infrastructure.
        </div>
      </div>
    </footer>
  );
}
