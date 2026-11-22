import { useEffect, useState } from 'react';
import { FileText, LocateFixed, MapPin, PlusCircle, RefreshCw, Search } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Alert from '../components/ui/Alert';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { createRequest, previewRoute } from '../api/dispatch';
import { listHospitals } from '../api/hospitals';
import { useAuth } from '../auth/AuthContext';
import { useRequests } from '../hooks/useRequests';
import { formatTimestamp } from '../utils/format';

const provinces = ['', 'Punjab', 'Sindh', 'Khyber Pakhtunkhwa', 'Balochistan', 'Islamabad Capital Territory', 'Gilgit-Baltistan', 'Azad Jammu and Kashmir'];
const blank = { emergency_mode: 'EMERGENCY', emergency_notes: '', origin_latitude: '', origin_longitude: '', origin_address: '', origin_city: '', location_source: '', hospital_id: '' };

function Status({ value }) { return <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">{value}</span>; }

export default function Requests() {
  const { user } = useAuth(); const ambulanceUser = user?.role === 'AMBULANCE';
  const { requests, loading, error, refetch } = useRequests(10000);
  const [form, setForm] = useState(blank); const [hospitals, setHospitals] = useState([]); const [hospitalQuery, setHospitalQuery] = useState(''); const [province, setProvince] = useState('');
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState(''); const [formError, setFormError] = useState(''); const [preview, setPreview] = useState(null); const [selectedHospital, setSelectedHospital] = useState(null);
  const set = (key, value) => { setForm(current => ({ ...current, [key]: value })); setFormError(''); };
  const loadHospitals = async () => {
    try {
      const filters = { q: hospitalQuery || undefined, province: province || undefined, page_size: 100 };
      const allHospitals = [];
      let page = 1;
      let hasMore = true;
      while (hasMore) {
        const data = await listHospitals({ ...filters, page });
        allHospitals.push(...(data.items || []));
        hasMore = Boolean(data.has_more);
        page += 1;
      }
      setHospitals(allHospitals);
    } catch (err) { setFormError(err.message); }
  };
  useEffect(() => { const timer = setTimeout(loadHospitals, 200); return () => clearTimeout(timer); }, [hospitalQuery, province]);
  const selected = selectedHospital || hospitals.find(item => item.id === form.hospital_id);
  const locate = () => {
    if (!navigator.geolocation) return setFormError('GPS is not supported by this browser. Select a location manually.');
    navigator.geolocation.getCurrentPosition(({ coords }) => { set('origin_latitude', coords.latitude.toFixed(6)); set('origin_longitude', coords.longitude.toFixed(6)); set('location_source', 'GPS'); }, () => setFormError('Location could not be obtained. Enter or select your location manually.'), { enableHighAccuracy: true, timeout: 10000 });
  };
  const requestPreview = async () => { if (!form.origin_latitude || !form.origin_longitude || !form.hospital_id) return setFormError('Select your current location and a destination hospital first.'); try { setPreview(await previewRoute({ origin_latitude: Number(form.origin_latitude), origin_longitude: Number(form.origin_longitude), hospital_id: form.hospital_id })); } catch (err) { setFormError(err.message); } };
  const submit = async event => { event.preventDefault(); if (!form.hospital_id || !form.origin_latitude || !form.origin_longitude || !form.location_source) return setFormError('Current location and destination hospital are required.'); setSaving(true); try { const result = await createRequest({ ...form, origin_latitude: Number(form.origin_latitude), origin_longitude: Number(form.origin_longitude) }); setMessage(`Emergency request ${result.request_id} has been submitted and is awaiting dispatch review.`); setForm(blank); setPreview(null); refetch(); } catch (err) { setFormError(err.message); } finally { setSaving(false); } };
  return <div className="min-h-screen bg-[#f6f8f7] flex"><Sidebar /><div className="flex-1 lg:pl-64"><header className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-5 py-4"><div className="flex items-center gap-2"><FileText className="text-[#087f5b]" /><div><h1 className="font-bold">Emergency Requests</h1><p className="text-xs text-gray-500">Real-world locations and verified directory destinations</p></div></div><button onClick={refetch} className="rounded p-2 hover:bg-gray-100"><RefreshCw className="h-4 w-4" /></button></header><main className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">{message && <Alert variant="success" title="Request submitted">{message}</Alert>}{error && <Alert variant="error">{error}</Alert>}
    {ambulanceUser ? <form onSubmit={submit} className="space-y-5"><Card><h2 className="font-bold">1. Ambulance information</h2><div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm"><b>LifeLane ID:</b> {user?.ambulance?.lifelane_id || 'Loading linked registration…'} <span className="ml-3"><Status value={user?.ambulance?.status || 'REGISTERED'} /></span></div></Card>
      <Card><h2 className="font-bold">2. Emergency details</h2><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Emergency type<select value={form.emergency_mode} onChange={e => set('emergency_mode', e.target.value)} className="mt-1 w-full rounded border p-2"><option>EMERGENCY</option><option>URGENT</option><option>ROUTINE</option></select></label><label className="text-sm font-medium">Notes (optional)<input value={form.emergency_notes} onChange={e => set('emergency_notes', e.target.value)} className="mt-1 w-full rounded border p-2" placeholder="Patient or dispatch notes" /></label></div></Card>
      <Card><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">3. Current location</h2><p className="text-sm text-gray-500">Use GPS, or enter a location manually if GPS is unavailable.</p></div><Button type="button" onClick={locate}><LocateFixed className="mr-1 inline h-4 w-4" />Use GPS</Button></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm">Latitude<input required type="number" step="any" value={form.origin_latitude} onChange={e => { set('origin_latitude', e.target.value); set('location_source', 'MANUAL'); }} className="mt-1 w-full rounded border p-2" /></label><label className="text-sm">Longitude<input required type="number" step="any" value={form.origin_longitude} onChange={e => { set('origin_longitude', e.target.value); set('location_source', 'MANUAL'); }} className="mt-1 w-full rounded border p-2" /></label><label className="text-sm">Readable address<input value={form.origin_address} onChange={e => set('origin_address', e.target.value)} className="mt-1 w-full rounded border p-2" placeholder="Address or landmark" /></label><label className="text-sm">City<input value={form.origin_city} onChange={e => set('origin_city', e.target.value)} className="mt-1 w-full rounded border p-2" placeholder="City" /></label></div>{form.location_source && <p className="mt-3 text-sm font-medium text-[#087f5b]"><MapPin className="inline h-4 w-4" /> {form.location_source === 'GPS' ? 'GPS-based location' : 'Manually selected location'}</p>}</Card>
      <Card><h2 className="font-bold">4. Destination hospital</h2><p className="text-sm text-gray-500">Directory coverage reflects imported source records and does not claim complete national coverage.</p><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" /><input value={hospitalQuery} onChange={e => setHospitalQuery(e.target.value)} className="w-full rounded border py-2 pl-9 pr-2" placeholder="Search hospital or city" /></label><select value={province} onChange={e => setProvince(e.target.value)} className="rounded border p-2"><option value="">All provinces and territories</option>{provinces.slice(1).map(value => <option key={value}>{value}</option>)}</select></div><label className="mt-3 block text-sm font-medium">Select hospital<select required value={form.hospital_id} onChange={e => { const hospital = hospitals.find(item => item.id === e.target.value) || null; setSelectedHospital(hospital); set('hospital_id', e.target.value); }} className="mt-1 w-full rounded border bg-white p-2"><option value="">Choose a destination hospital ({hospitals.length} available)</option>{hospitals.map(item => <option key={item.id} value={item.id}>{item.name} — {item.city}, {item.province}</option>)}</select></label>{!hospitals.length && <p className="mt-3 text-sm text-gray-500">No imported hospitals match these filters.</p>}{selected && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm"><b>Selected destination:</b> {selected.name} — {selected.city}, {selected.province}</div>}</Card>
      <Card><h2 className="font-bold">5. Route preview</h2><p className="mt-1 text-sm text-gray-500">Preview uses real road data between your selected location and hospital.</p><Button type="button" variant="secondary" onClick={requestPreview} className="mt-3">Confirm destination & preview</Button>{preview && <div className="mt-3 rounded bg-emerald-50 p-3 text-sm text-emerald-900"><b>{preview.destination?.name}</b><div className="mt-1">{preview.distance_km != null && <><b>{preview.distance_km} km</b> · <b>about {preview.eta_minutes} min</b> · </>}{preview.message}</div>{preview.provider && <p className="mt-1 text-xs text-emerald-700">Road route provided by {preview.provider}; estimates can change with road conditions.</p>}</div>}</Card>
      {formError && <Alert variant="error">{formError}</Alert>}<div className="flex justify-end"><Button type="submit" loading={saving} disabled={saving}><PlusCircle className="mr-1 inline h-4 w-4" />Submit emergency request</Button></div></form> : <Card><h2 className="font-bold">Emergency request monitoring</h2><p className="mt-1 text-sm text-gray-500">Use Management for administrative review and priority authorization.</p></Card>}
    <Card padding={false}><div className="border-b p-4"><h2 className="font-bold">Request history</h2></div>{loading ? <LoadingSpinner /> : <div className="overflow-auto"><table className="w-full text-left text-sm"><thead className="bg-gray-50 text-xs uppercase text-gray-500"><tr><th className="p-3">Request</th><th className="p-3">Ambulance</th><th className="p-3">Destination</th><th className="p-3">Location</th><th className="p-3">Status</th><th className="p-3">Created</th></tr></thead><tbody>{requests.map(row => <tr key={row.id} className="border-t"><td className="p-3 font-mono text-xs">{row.request_id}</td><td className="p-3">{row.ambulance_id}</td><td className="p-3">{row.hospital_id}</td><td className="p-3">{row.origin_city || row.origin_address || 'Not recorded'}</td><td className="p-3"><Status value={row.status} /></td><td className="p-3">{formatTimestamp(row.created_at)}</td></tr>)}</tbody></table>{!requests.length && <p className="p-5 text-sm text-gray-500">No emergency requests yet.</p>}</div>}</Card>
  </main></div></div>;
}
