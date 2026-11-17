import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

function processDetections(detections) {
  // Group last 20 detections by junction
  const grouped = {};
  detections.slice(0, 20).forEach((d) => {
    const key = d.junction_id || 'Unknown';
    if (!grouped[key]) grouped[key] = { junction: key, siren: 0, no_siren: 0 };
    if (d.is_siren) grouped[key].siren++;
    else grouped[key].no_siren++;
  });
  return Object.values(grouped);
}

export default function DetectionChart({ detections = [] }) {
  const data = processDetections(detections);

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        No detection data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="junction" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="siren" name="Siren" fill="#C0392B" radius={[3, 3, 0, 0]} />
        <Bar dataKey="no_siren" name="No Siren" fill="#087F5B" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
