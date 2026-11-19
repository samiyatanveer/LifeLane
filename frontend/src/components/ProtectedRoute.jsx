import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
export default function ProtectedRoute({ children, roles }) { const { user, loading } = useAuth(); const location = useLocation(); if (loading) return <div className="min-h-screen grid place-items-center">Loading secure session…</div>; if (!user) return <Navigate to="/login" state={{ from: location }} replace />; if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />; return children; }
