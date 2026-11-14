export default function Card({ children, className = '', padding = true }) {
  return (
    <div
      className={`premium-card bg-white rounded-2xl shadow-sm border border-gray-200 ${padding ? 'p-5 sm:p-6' : ''} ${className}`}
    >
      {children}
    </div>
  );
}
