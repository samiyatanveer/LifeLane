import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react';
import { useState } from 'react';

const VARIANTS = {
  info: { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-800', icon: Info },
  warning: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800', icon: AlertTriangle },
  error: { bg: 'bg-red-50 border-red-200', text: 'text-red-800', icon: AlertCircle },
  success: { bg: 'bg-green-50 border-green-200', text: 'text-green-800', icon: CheckCircle },
};

export default function Alert({ variant = 'info', title, children, dismissible = false, className = '' }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const { bg, text, icon: Icon } = VARIANTS[variant] || VARIANTS.info;

  return (
    <div className={`flex gap-3 p-4 rounded-lg border ${bg} ${className}`} role="alert">
      <Icon className={`flex-shrink-0 w-5 h-5 mt-0.5 ${text}`} />
      <div className={`flex-1 text-sm ${text}`}>
        {title && <p className="font-semibold mb-1">{title}</p>}
        <div>{children}</div>
      </div>
      {dismissible && (
        <button
          onClick={() => setDismissed(true)}
          className={`flex-shrink-0 ${text} hover:opacity-70 transition-opacity`}
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
