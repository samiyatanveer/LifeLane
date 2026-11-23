import { createContext, useContext, useEffect, useState } from 'react';
import { getMe, login as loginRequest, logout as logoutRequest } from '../api/auth';
import client from '../api/client';
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); const [loading, setLoading] = useState(true);
  const setToken = (token) => { if (token) localStorage.setItem('lifelane-token', token); else localStorage.removeItem('lifelane-token'); client.defaults.headers.common.Authorization = token ? `Bearer ${token}` : undefined; };
  useEffect(() => { const token = localStorage.getItem('lifelane-token'); if (!token) { setLoading(false); return; } setToken(token); getMe().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false)); }, []);
  const acceptAuthResponse = (result) => { setToken(result.access_token); setUser(result.user); return result; };
  const login = async (credentials) => acceptAuthResponse(await loginRequest(credentials));
  const logout = async () => { try { await logoutRequest(); } finally { setToken(null); setUser(null); } };
  return <AuthContext.Provider value={{ user, loading, login, logout, acceptAuthResponse }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
