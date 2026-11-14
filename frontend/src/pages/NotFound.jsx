import { Link } from 'react-router-dom';
import { Ambulance, ArrowLeft } from 'lucide-react';
import Button from '../components/ui/Button';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#F6F8F7] flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 rounded-2xl bg-green-100 flex items-center justify-center mb-6 text-[#087F5B]">
        <Ambulance className="w-8 h-8" />
      </div>
      <h1 className="text-4xl font-extrabold text-gray-900 mb-2">404</h1>
      <h2 className="text-xl font-bold text-gray-700 mb-3">Page Not Found</h2>
      <p className="text-sm text-gray-500 max-w-sm mb-8">
        The route you requested does not exist or has been relocated within the LifeLane traffic priority simulation.
      </p>
      <Link to="/">
        <Button className="flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Landing Page</span>
        </Button>
      </Link>
    </div>
  );
}
