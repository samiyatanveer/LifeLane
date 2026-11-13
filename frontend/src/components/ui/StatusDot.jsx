const DOT_COLORS = {
  green: 'bg-green-500',
  red: 'bg-red-500',
  amber: 'bg-amber-500',
  blue: 'bg-blue-500',
  gray: 'bg-gray-400',
};

export default function StatusDot({ color = 'green', animate = true, size = 'md' }) {
  const sizeClass = size === 'sm' ? 'w-2 h-2' : size === 'lg' ? 'w-4 h-4' : 'w-3 h-3';
  const dotColor = DOT_COLORS[color] || 'bg-gray-400';

  return (
    <span className="relative inline-flex items-center justify-center">
      {animate && (
        <span className={`absolute inline-flex rounded-full opacity-75 animate-ping ${sizeClass} ${dotColor}`} />
      )}
      <span className={`relative inline-flex rounded-full ${sizeClass} ${dotColor}`} />
    </span>
  );
}
