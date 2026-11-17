// Badge component: auto-colored by state string
const STATE_CLASS_MAP = {
  NORMAL: 'bg-green-100 text-green-800 border-green-200',
  SUSPECTED: 'bg-amber-100 text-amber-800 border-amber-200',
  CONFIRMED: 'bg-amber-100 text-amber-800 border-amber-200',
  PREPARING: 'bg-orange-100 text-orange-800 border-orange-200',
  SERVING: 'bg-red-100 text-red-800 border-red-200',
  RECOVERING: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  ACTIVE: 'bg-green-100 text-green-800 border-green-200',
  PENDING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  COMPLETED: 'bg-gray-100 text-gray-700 border-gray-200',
  CANCELLED: 'bg-gray-100 text-gray-500 border-gray-200',
  REAL: 'bg-green-100 text-green-800 border-green-200',
  SYNTHETIC: 'bg-amber-100 text-amber-800 border-amber-200',
  MOCK: 'bg-gray-100 text-gray-700 border-gray-200',
  MOCK_YAMNET: 'bg-gray-100 text-gray-700 border-gray-200',
};

const VARIANT_CLASS_MAP = {
  default: 'bg-gray-100 text-gray-700 border-gray-200',
  primary: 'bg-green-100 text-green-800 border-green-200',
  warning: 'bg-amber-100 text-amber-800 border-amber-200',
  danger: 'bg-red-100 text-red-800 border-red-200',
  info: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  simulation: 'bg-red-50 text-red-700 border-red-300 font-bold',
};

export default function Badge({ children, state, variant = 'default', className = '' }) {
  const cls = state
    ? STATE_CLASS_MAP[state] || VARIANT_CLASS_MAP.default
    : VARIANT_CLASS_MAP[variant];

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls} ${className}`}
    >
      {children || state}
    </span>
  );
}
