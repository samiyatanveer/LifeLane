import { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../api/auth';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const submit = async (event) => { event.preventDefault(); if (loading) return; if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setError('Enter a valid email address.'); return; } setLoading(true); setError(''); try { const response = await forgotPassword({ email: email.trim() }); setMessage(response.message); } catch (err) { setError(err.message === 'Network Error' ? 'Network error. Check your connection and try again.' : err.message); } finally { setLoading(false); } };
  return <main className="min-h-screen grid place-items-center bg-[#f6f8f7] p-5"><section className="w-full max-w-md rounded-3xl bg-white p-7 shadow-xl"><h1 className="text-2xl font-extrabold text-[#063d2b]">Forgot your password?</h1><p className="mt-2 text-sm text-gray-600">Enter the email address registered with your LifeLane account.</p><form onSubmit={submit} className="mt-6 space-y-4"><label className="block text-sm font-semibold text-gray-700">Email address<input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" className="mt-1.5 w-full rounded-xl border border-gray-300 px-3 py-2.5" /></label>{error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}{message && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">{message}</p>}<button disabled={loading || !!message} className="w-full rounded-xl bg-[#087f5b] py-3 font-bold text-white disabled:opacity-60">{loading ? 'Sending…' : 'Send reset link'}</button></form><Link to="/login" className="mt-5 inline-block text-sm font-semibold text-[#087f5b]">Back to sign in</Link></section></main>;
}
