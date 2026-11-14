const VARIANTS = {
  primary: 'bg-[#087F5B] hover:bg-[#0B5D3B] text-white border-transparent disabled:opacity-50',
  secondary: 'bg-white hover:bg-gray-50 text-[#087F5B] border-[#087F5B] disabled:opacity-50',
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
      className={`inline-flex items-center justify-center gap-2 font-medium rounded-lg border transition-colors cursor-pointer
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
