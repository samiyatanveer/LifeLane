const VARIANTS = {
  primary: 'bg-gradient-to-r from-[#063d2b] to-[#087f5b] hover:brightness-110 text-white border-transparent disabled:opacity-50 shadow-sm shadow-emerald-900/20',
  secondary: 'bg-white hover:bg-green-50 text-[#087f5b] border-green-200 disabled:opacity-50',
  danger: 'bg-red-600 hover:bg-red-700 text-white border-transparent disabled:opacity-50',
  ghost: 'bg-transparent hover:bg-gray-100 text-gray-700 border-transparent disabled:opacity-50',
};

const SIZES = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-2 font-medium rounded-xl border transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2
        ${VARIANTS[variant]} ${SIZES[size]} ${className}
        disabled:cursor-not-allowed`}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
