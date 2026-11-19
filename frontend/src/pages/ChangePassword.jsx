import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { changePassword } from '../api/auth';
import { useAuth } from '../auth/AuthContext';

export default function ChangePassword() {
  const navigate = useNavigate(); const { logout } = useAuth();
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault(); if (loading) return;
    if (form.new_password.length < 8 || !/[A-Za-z]/.test(form.new_password) || !/\d/.test(form.new_password)) { setError('Use at least 8 characters, including a letter and a number.'); return; }
    if (form.new_password !== form.confirm_password) { setError('New passwords do not match.'); return; }
    setLoading(true); setError('');
    try { await changePassword({ current_password: form.current_password, new_password: form.new_password }); await logout().catch(() => {}); navigate('/login', { replace: true }); }
    catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  return <main className="min-h-screen grid place-items-center bg-[#f6f8f7] p-5"><section className="w-full max-w-md rounded-3xl bg-white p-7 shadow-xl"><div className="flex items-center gap-3 text-[#063d2b]"><span className="grid h-11 w-11 place-items-center rounded-xl bg-[#087f5b] text-white"><KeyRound /></span><div><h1 className="text-2xl font-extrabold">Change password</h1><p className="text-sm text-gray-500">Confirm your current password to continue.</p></div></div><form onSubmit={submit} className="mt-7 space-y-4"><label className="block text-sm font-semibold text-gray-700">Current password<input required name="current_password" type="password" autoComplete="current-password" value={form.current_password} onChange={update} className="mt-1.5 w-full rounded-xl border border-gray-300 px-3 py-2.5" /></label><label className="block text-sm font-semibold text-gray-700">New password<input required name="new_password" type="password" autoComplete="new-password" value={form.new_password} onChange={update} className="mt-1.5 w-full rounded-xl border border-gray-300 px-3 py-2.5" /><span className="mt-1 block text-xs font-normal text-gray-500">At least 8 characters, including a letter and a number.</span></label><label className="block text-sm font-semibold text-gray-700">Confirm new password<input required name="confirm_password" type="password" autoComplete="new-password" value={form.confirm_password} onChange={update} className="mt-1.5 w-full rounded-xl border border-gray-300 px-3 py-2.5" /></label>{error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<button disabled={loading} className="w-full rounded-xl bg-[#087f5b] py-3 font-bold text-white disabled:opacity-60">{loading ? 'Updating password...' : 'Update password'}</button></form><Link to="/dashboard" className="mt-5 inline-block text-sm font-semibold text-[#087f5b]">Back to dashboard</Link></section></main>;
}
