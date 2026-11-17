import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

const STATE_COLORS_MAP = {
  NORMAL: '#087F5B',
  SUSPECTED: '#D97706',
  CONFIRMED: '#D97706',
  PREPARING: '#EA580C',
  SERVING: '#C0392B',
  RECOVERING: '#0D9488',
};

export default function SignalStateChart({ signals = [] }) {
  if (!signals.length) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
        No signal data
      </div>
    );
  }

  const data = signals.map((s) => ({
    id: s.junction_id || s.id,
    state: s.state || 'NORMAL',
    value: 1,
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="id" tick={{ fontSize: 12 }} />
        <YAxis hide />
        <Tooltip
          formatter={(_, __, props) => [props.payload.state, 'State']}
        />
        <Bar dataKey="value" name="State" radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={STATE_COLORS_MAP[entry.state] || '#6b7280'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
