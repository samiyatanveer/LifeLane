import { Inbox } from 'lucide-react';

export default function EmptyState({ title = 'No data', message = 'Nothing to display yet.', icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icon className="w-10 h-10 text-gray-300 mb-3" />
      <h3 className="text-sm font-semibold text-gray-600">{title}</h3>
      <p className="text-xs text-gray-400 mt-1 max-w-xs">{message}</p>
    </div>
  );
}
