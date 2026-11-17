import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';

const KM = 90;
const TRAFFIC_COLORS = ['#22B866', '#E6A410', '#D62839']; // Light, Moderate, Heavy
const TRAFFIC_FACTORS = [1.0, 1.8, 3.2];

const HOSPITAL_NAMES = {
  H1: 'City General Hospital (JPMC)',
  H2: 'Riverside Trauma Centre',
  H3: 'North Care Emergency Hospital',
};

const NODES = {
  A: [80, 380],
  n1: [230, 380],
  n2: [400, 380],
  n3: [570, 380],
  n4: [230, 250],
  n5: [400, 250],
  n6: [570, 250],
  n7: [230, 110],
  n8: [400, 110],
  n9: [570, 110],
  H1: [730, 110],
  H2: [730, 380],
  H3: [80, 110],
};

const INITIAL_EDGES = [
  ['A', 'n1', 0], ['n1', 'n2', 1], ['n2', 'n3', 2], ['n3', 'H2', 0],
  ['n4', 'n5', 2], ['n5', 'n6', 1], ['n7', 'n8', 0], ['n8', 'n9', 0],
  ['n9', 'H1', 0], ['H3', 'n7', 0], ['n1', 'n4', 0], ['n4', 'n7', 1],
  ['n2', 'n5', 2], ['n5', 'n8', 0], ['n3', 'n6', 1], ['n6', 'n9', 0],
  ['A', 'n4', 1], ['n6', 'H1', 2], ['n4', 'H3', 0],
];

export default function RoutePlanner() {
  const [edges, setEdges] = useState(INITIAL_EDGES);
  const [startPoint, setStartPoint] = useState('A');
  const [hospitalMode, setHospitalMode] = useState('reg'); // 'reg' or 'near'
  const [isTripActive, setIsTripActive] = useState(false);
  const [tripEta, setTripEta] = useState('--');
  const [tripStatusMsg, setTripStatusMsg] = useState('');
  const [ambPos, setAmbPos] = useState(NODES.A);

  const pathRef = useRef(null);
  const tripAnimRef = useRef(null);

  // Helper calculations
  const getLen = useCallback((u, v) => {
    return Math.hypot(NODES[u][0] - NODES[v][0], NODES[u][1] - NODES[v][1]);
  }, []);

  const findEdge = useCallback((u, v, currentEdges) => {
    return currentEdges.find(
      (e) => (e[0] === u && e[1] === v) || (e[0] === v && e[1] === u)
    );
  }, []);

  // Dijkstra algorithm for shortest or fastest
  const dijkstra = useCallback((src, dest, weightFn, currentEdges) => {
    const dist = {};
    const prev = {};
    const nodes = Object.keys(NODES);
    nodes.forEach((n) => (dist[n] = 1e9));
    dist[src] = 0;
    const unvisited = new Set(nodes);

    while (unvisited.size > 0) {
      let u = null;
      unvisited.forEach((node) => {
        if (u === null || dist[node] < dist[u]) u = node;
      });
      unvisited.delete(u);
      if (u === dest) break;

      currentEdges.forEach((e) => {
        if (e[0] !== u && e[1] !== u) return;
        const v = e[0] === u ? e[1] : e[0];
        if (v.startsWith('H') && v !== dest) return; // avoid cutting through other hospitals
        const weight = weightFn(e);
        const alt = dist[u] + weight;
        if (alt < dist[v]) {
          dist[v] = alt;
          prev[v] = u;
        }
      });
    }

    const path = [dest];
    let curr = dest;
    while (curr !== src && prev[curr]) {
      curr = prev[curr];
      path.unshift(curr);
    }
    return path;
  }, []);

  const wTime = useCallback((e) => (getLen(e[0], e[1]) / KM) * TRAFFIC_FACTORS[e[2]] * 1.5, [getLen]);
  const wDist = useCallback((e) => getLen(e[0], e[1]) / KM, [getLen]);

  const getStats = useCallback((path, currentEdges) => {
    let km = 0;
    let mins = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const e = findEdge(path[i], path[i + 1], currentEdges);
      if (e) {
        km += wDist(e);
        mins += wTime(e);
      }
    }
    return { km, mins };
  }, [findEdge, wDist, wTime]);

  // Determine current destination hospital
  const targetHospital = useMemo(() => {
    if (hospitalMode === 'reg') return 'H1';
    let bestHosp = 'H1';
    let bestTime = 1e9;
    ['H1', 'H2', 'H3'].forEach((h) => {
      const p = dijkstra(startPoint, h, wTime, edges);
      const { mins } = getStats(p, edges);
      if (mins < bestTime) {
        bestTime = mins;
        bestHosp = h;
      }
    });
    return bestHosp;
  }, [hospitalMode, startPoint, edges, dijkstra, wTime, getStats]);

  // Compute Fast (Time-optimized) and Short (Distance-only) routes
  const fastPath = useMemo(() => dijkstra(startPoint, targetHospital, wTime, edges), [startPoint, targetHospital, wTime, edges, dijkstra]);
  const shortPath = useMemo(() => dijkstra(startPoint, targetHospital, wDist, edges), [startPoint, targetHospital, wDist, edges, dijkstra]);

  const fastStats = useMemo(() => getStats(fastPath, edges), [fastPath, edges, getStats]);
  const shortStats = useMemo(() => getStats(shortPath, edges), [shortPath, edges, getStats]);

  const isSameRoute = useMemo(() => fastPath.join() === shortPath.join(), [fastPath, shortPath]);

  // Heavy roads avoided
  const heavyRoadsAvoided = useMemo(() => {
    const fastSet = new Set();
    const shortSet = new Set();
    for (let i = 0; i < fastPath.length - 1; i++) {
      const e = findEdge(fastPath[i], fastPath[i + 1], edges);
      if (e && e[2] === 2) fastSet.add(e);
    }
    for (let i = 0; i < shortPath.length - 1; i++) {
      const e = findEdge(shortPath[i], shortPath[i + 1], edges);
      if (e && e[2] === 2) shortSet.add(e);
    }
    return [...shortSet].filter((e) => !fastSet.has(e)).length;
  }, [fastPath, shortPath, edges, findEdge]);

  // Click on a road to cycle traffic congestion
  const handleRoadClick = (index) => {
    if (isTripActive) return;
    setEdges((prev) => {
      const updated = [...prev];
      updated[index] = [updated[index][0], updated[index][1], (updated[index][2] + 1) % 3];
      return updated;
    });
  };

  // Randomize all road traffic
  const handleRandomizeTraffic = () => {
    if (isTripActive) return;
    setEdges((prev) =>
      prev.map(([u, v]) => {
        const r = Math.random();
        const traffic = r < 0.4 ? 0 : r < 0.72 ? 1 : 2;
        return [u, v, traffic];
      })
    );
  };

  // Reset ambulance position when startPoint changes
  useEffect(() => {
    if (!isTripActive) {
      setAmbPos(NODES[startPoint]);
      setTripEta(`${Math.round(fastStats.mins)} min`);
    }
  }, [startPoint, isTripActive, fastStats.mins]);

  // Trip simulation along SVG path
  const handleStartTrip = () => {
    if (isTripActive || !pathRef.current) return;
    setIsTripActive(true);
    setTripStatusMsg('Ambulance en route under coordinated preemption...');

    const pathEl = pathRef.current;
    const totalLength = pathEl.getTotalLength();
    const initialMins = fastStats.mins;
    const duration = 6500;
    let startTs = null;

    const animate = (ts) => {
      if (!startTs) startTs = ts;
      const progress = Math.min((ts - startTs) / duration, 1);
      const point = pathEl.getPointAtLength(totalLength * progress);
      setAmbPos([point.x, point.y]);

      const remainingMin = Math.max(0, Math.round(initialMins * (1 - progress)));
      setTripEta(`${remainingMin} min`);

      if (progress < 1) {
        tripAnimRef.current = requestAnimationFrame(animate);
      } else {
        setIsTripActive(false);
        setTripEta('Arrived');
        setTripStatusMsg(`Arrived safely at ${HOSPITAL_NAMES[targetHospital]}. Emergency room prepped.`);
      }
    };

    tripAnimRef.current = requestAnimationFrame(animate);
  };

  useEffect(() => {
    return () => {
      if (tripAnimRef.current) cancelAnimationFrame(tripAnimRef.current);
    };
  }, []);

  const dPathString = fastPath.map((k, i) => `${i === 0 ? 'M' : 'L'} ${NODES[k][0]} ${NODES[k][1]}`).join(' ');
  const shortPointsString = shortPath.map((k) => NODES[k].join(',')).join(' ');
  const fastPointsString = fastPath.map((k) => NODES[k].join(',')).join(' ');

  return (
    <section className="py-12 wrap">
      <h2>The quickest road to the registered hospital</h2>
      <p className="mt-2 mb-6">
        Roads are colored by real-time traffic congestion. LifeLane picks the route that gets the ambulance there soonest, not only the shortest distance. <strong>Click any road</strong> to change its traffic level and watch the recommended corridor adapt.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* SVG Interactive Road Map (8 Cols) */}
        <div className="lg:col-span-8 life-card p-4 sm:p-6">
          <svg
            viewBox="0 0 800 460"
            role="img"
            aria-label="Map of roads colored by traffic with recommended ambulance corridor"
            className="w-full h-auto block rounded-xl bg-[var(--tint)]"
          >
            {/* Background Rect */}
            <rect width="800" height="460" rx="16" fill="var(--tint)" />

            {/* Clickable Road Segments */}
            <g id="roads">
              {edges.map((e, idx) => {
                const [u, v, traffic] = e;
                return (
                  <line
                    key={`${u}-${v}-${idx}`}
                    x1={NODES[u][0]}
                    y1={NODES[u][1]}
                    x2={NODES[v][0]}
                    y2={NODES[v][1]}
                    stroke={TRAFFIC_COLORS[traffic]}
                    strokeWidth="13"
                    strokeLinecap="round"
                    opacity="0.88"
                    className="cursor-pointer hover:opacity-100 transition-opacity"
                    onClick={() => handleRoadClick(idx)}
                  >
                    <title>Click to toggle road traffic</title>
                  </line>
                );
              })}
            </g>

            {/* Shortest Route (Dashed Gray) if different from Fastest */}
            {!isSameRoute && (
              <polyline
                points={shortPointsString}
                fill="none"
                stroke="#4C6355"
                strokeWidth="3"
                strokeDasharray="4 8"
                strokeLinecap="round"
              />
            )}

            {/* Fastest Route Underlay & Flowing Animated Path */}
            <polyline
              points={fastPointsString}
              fill="none"
              stroke="#ffffff"
              strokeWidth="9"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            <polyline
              points={fastPointsString}
              fill="none"
              stroke="var(--g)"
              strokeWidth="5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            <polyline
              points={fastPointsString}
              fill="none"
              stroke="#ffffff"
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              className="flow"
            />

            {/* Hidden SVG Path used by getPointAtLength for smooth interpolation */}
            <path ref={pathRef} d={dPathString} fill="none" stroke="none" />

            {/* Nodes & Junctions */}
            <g id="nodes">
              {Object.keys(NODES).map((k) => {
                const [x, y] = NODES[k];
                if (k.startsWith('H')) {
                  const isReg = k === 'H1';
                  return (
                    <g key={k}>
                      <rect
                        x={x - 19}
                        y={y - 19}
                        width="38"
                        height="38"
                        rx="9"
                        fill="#ffffff"
                        stroke={isReg ? 'var(--gold)' : 'var(--g)'}
                        strokeWidth={isReg ? 5 : 3}
                      />
                      <text
                        x={x}
                        y={y + 6}
                        textAnchor="middle"
                        fontSize="18"
                        fontWeight="800"
                        fill="var(--g)"
                      >
                        H
                      </text>
                      <text
                        x={x}
                        y={y + 36}
                        textAnchor="middle"
                        fontSize="11"
                        fontWeight="700"
                        fill="var(--ink)"
                      >
                        {HOSPITAL_NAMES[k]} {isReg ? '(registered)' : ''}
                      </text>
                    </g>
                  );
                } else if (k === 'A' || k === 'n2' || k === 'n3') {
                  const label = { A: 'Point A', n2: 'Point B', n3: 'Point C' }[k];
                  const isSelectedStart = k === startPoint;
                  return (
                    <g key={k}>
                      <circle
                        cx={x}
                        cy={y}
                        r={isSelectedStart ? 11 : 8}
                        fill="var(--surface)"
                        stroke={isSelectedStart ? 'var(--red)' : 'var(--ink)'}
                        strokeWidth="3"
                      />
                      <text
                        x={x}
                        y={y + 26}
                        textAnchor="middle"
                        fontSize="11"
                        fontWeight="700"
                        fill="var(--ink)"
                      >
                        {label}
                      </text>
                    </g>
                  );
                }
                return <circle key={k} cx={x} cy={y} r="4" fill="var(--mute)" opacity="0.7" />;
              })}
            </g>

            {/* Animated Ambulance Icon Indicator */}
            <g transform={`translate(${ambPos[0]} ${ambPos[1]})`}>
              <circle r="13" fill="var(--red)" stroke="#ffffff" strokeWidth="3" />
              <path d="M -5 0 h 10 M 0 -5 v 10" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" />
            </g>
          </svg>

          {/* Map Legend */}
          <div className="flex flex-wrap gap-4 pt-3 text-xs font-semibold text-[var(--mute)]">
            <span className="flex items-center gap-1.5">
              <i className="w-5 h-2 rounded-full inline-block bg-[#22B866]" /> Light Traffic
            </span>
            <span className="flex items-center gap-1.5">
              <i className="w-5 h-2 rounded-full inline-block bg-[#E6A410]" /> Moderate Delay
            </span>
            <span className="flex items-center gap-1.5">
              <i className="w-5 h-2 rounded-full inline-block bg-[#D62839]" /> Heavy Congestion
            </span>
            <span className="flex items-center gap-1.5">
              <i className="w-5 h-2 rounded-full inline-block bg-[var(--g)]" /> LifeLane Recommended Route
            </span>
            <span className="flex items-center gap-1.5">
              <i className="w-5 h-2 rounded-full inline-block border-t-2 border-dashed border-[#4C6355]" /> Shortest Distance Route
            </span>
          </div>
          <small className="block mt-2 text-xs text-[var(--mute)]">
            Simulation map of Karachi Central district. Click any road segment to dynamically alter traffic density.
          </small>
        </div>

        {/* Side Controls & Analytics Panel (4 Cols) */}
        <div className="lg:col-span-4 flex flex-col gap-5">
          {/* Dispatch Destination Settings */}
          <div className="life-card">
            <h3>Registered Destination</h3>
            <p className="text-sm mt-1 mb-3">
              Ambulance <strong>AMB-014</strong> registered with emergency department:
            </p>

            {/* Hospital Mode Toggle */}
            <div className="flex gap-2 p-1 rounded-xl bg-[var(--tint)] mb-4">
              <button
                onClick={() => setHospitalMode('reg')}
                className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all ${
                  hospitalMode === 'reg' ? 'bg-[var(--g)] text-white' : 'text-[var(--ink)] hover:bg-black/5'
                }`}
              >
                Registered Hospital
              </button>
              <button
                onClick={() => setHospitalMode('near')}
                className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all ${
                  hospitalMode === 'near' ? 'bg-[var(--g)] text-white' : 'text-[var(--ink)] hover:bg-black/5'
                }`}
              >
                Nearest Trauma Center
              </button>
            </div>

            {/* Start Point Selector */}
            <label htmlFor="startSelect" className="block text-xs font-bold text-[var(--mute)] uppercase tracking-wider mb-1">
              Ambulance Starting Location
            </label>
            <select
              id="startSelect"
              disabled={isTripActive}
              value={startPoint}
              onChange={(e) => setStartPoint(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] text-sm font-semibold focus:outline-none"
            >
              <option value="A">Point A (West Karachi Suburb)</option>
              <option value="n2">Point B (City Center Junction)</option>
              <option value="n3">Point C (East Industrial Sector)</option>
            </select>
          </div>

          {/* Real-Time Routing Summary */}
          <div className="life-card">
            <h3 className="text-base text-[var(--mute)]">
              {hospitalMode === 'reg' ? 'En Route to Registered Hospital' : 'En Route to Closest Emergency Center'}
            </h3>
            <p className="font-bold text-lg text-[var(--ink)] mt-0.5">
              {HOSPITAL_NAMES[targetHospital]}
            </p>

            <div className="grid grid-cols-2 gap-4 mt-4 pt-3 border-t border-[var(--line)]">
              <div>
                <span className="block font-black text-2xl leading-tight text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
                  {isTripActive ? tripEta : `${Math.round(fastStats.mins)} min`}
                </span>
                <small className="text-xs text-[var(--mute)]">Estimated Travel Time</small>
              </div>
              <div>
                <span className="block font-black text-2xl leading-tight text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
                  {fastStats.km.toFixed(1)} km
                </span>
                <small className="text-xs text-[var(--mute)]">Corridor Distance</small>
              </div>
            </div>

            {/* Dynamic Congestion Analysis Advice */}
            <p className="mt-4 text-xs font-medium text-[var(--ink)] bg-[var(--tint)] p-3 rounded-xl leading-relaxed">
              {tripStatusMsg ||
                (isSameRoute
                  ? 'The shortest route is also the quickest under current traffic flows.'
                  : `${heavyRoadsAvoided > 0 ? `Avoids ${heavyRoadsAvoided} heavily congested intersection${heavyRoadsAvoided > 1 ? 's' : ''}. ` : 'Routes around active grid bottlenecks. '}Saves approx ${Math.max(1, Math.round(shortStats.mins - fastStats.mins))} min compared to direct distance route.`)}
            </p>

            <div className="flex flex-wrap gap-2 mt-5">
              <button
                onClick={handleStartTrip}
                disabled={isTripActive}
                className="cta-btn flex-1 text-sm py-2.5"
              >
                {isTripActive ? 'Simulating trip...' : 'Start Trip'}
              </button>
              <button
                onClick={handleRandomizeTraffic}
                disabled={isTripActive}
                className="cta-btn alt text-sm py-2.5"
              >
                Randomize Traffic
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
