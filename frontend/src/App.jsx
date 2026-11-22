import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing'; import Login from './pages/Login'; import Dashboard from './pages/Dashboard';
import Ambulances from './pages/Ambulances'; import Requests from './pages/Requests'; import Signals from './pages/Signals'; import Detection from './pages/Detection'; import History from './pages/History';
import ProtectedRoute from './components/ProtectedRoute'; import RegisterAmbulance from './pages/RegisterAmbulance';
import Management from './pages/Management';
import ForgotPassword from './pages/ForgotPassword'; import ResetPassword from './pages/ResetPassword';
import ChangePassword from './pages/ChangePassword';
const Secure = ({ children, roles }) => <ProtectedRoute roles={roles}>{children}</ProtectedRoute>;
export default function App() { return <BrowserRouter><Routes>
  <Route path="/" element={<Landing />} /><Route path="/login" element={<Login />} /><Route path="/forgot-password" element={<ForgotPassword />} /><Route path="/reset-password" element={<ResetPassword />} /><Route path="/ambulances/register" element={<RegisterAmbulance />} />
  <Route path="/dashboard" element={<Secure><Dashboard /></Secure>} /><Route path="/detection" element={<Secure roles={['DISPATCHER','ADMIN']}><Detection /></Secure>} />
  <Route path="/change-password" element={<Secure><ChangePassword /></Secure>} />
  <Route path="/management" element={<Secure roles={['DISPATCHER','ADMIN']}><Management /></Secure>} />
  <Route path="/signals" element={<Secure roles={['DISPATCHER','ADMIN']}><Signals /></Secure>} /><Route path="/history" element={<Secure><History /></Secure>} />
  <Route path="/ambulances" element={<Secure roles={['DISPATCHER','ADMIN']}><Ambulances /></Secure>} /><Route path="/requests" element={<Secure><Requests /></Secure>} />
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes></BrowserRouter>; }
