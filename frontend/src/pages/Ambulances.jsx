import { useState } from 'react';
import { Menu, Ambulance, PlusCircle, RefreshCw, Copy, Check } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Alert from '../components/ui/Alert';
import EmptyState from '../components/ui/EmptyState';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { registerAmbulance } from '../api/dispatch';
import { useAmbulances } from '../hooks/useAmbulances';
import { formatTimestamp } from '../utils/format';

function CopyID({ id }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* ignore */
    }
  };
  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-mono font-bold text-[#087F5B] bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors cursor-pointer"
      title="Copy LifeLane ID"
    >
      <span>{id}</span>
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3 opacity-60" />}
    </button>
  );
}

const INITIAL_FORM = { registration_number: '', service_name: '', device_id: '' };

export default function Ambulances() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(null);

  const { ambulances, loading, error, refetch } = useAmbulances(15000);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setSubmitError(null);
  };

  const validate = () => {
    if (!form.registration_number.trim()) return 'Registration number is required.';
    if (!form.service_name.trim()) return 'Service name is required.';
    if (!form.device_id.trim()) return 'Device ID is required.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) { setSubmitError(err); return; }
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      const result = await registerAmbulance({
        registration_number: form.registration_number.trim(),
        service_name: form.service_name.trim(),
        device_id: form.device_id.trim(),
      });
      setSubmitSuccess(`Ambulance registered! LifeLane ID assigned: ${result.lifelane_id}`);
      setForm(INITIAL_FORM);
      setShowForm(false);
      refetch();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="ops-page min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        <header className="ops-header sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button className="lg:hidden p-2 rounded-md hover:bg-gray-100" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <Ambulance className="w-5 h-5 text-[#087F5B]" />
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-gray-900 text-lg truncate">Ambulance Registry</h1>
          </div>
          <button
            onClick={refetch}
            className="p-2 rounded-md hover:bg-gray-100 text-gray-500"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <Button
            size="sm"
            onClick={() => { window.location.assign('/ambulances/register'); }}
            className="flex items-center gap-1.5"
          >
            <PlusCircle className="w-4 h-4" />
            <span className="hidden sm:inline">Register Ambulance</span>
          </Button>
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">

          {/* Success banner */}
          {submitSuccess && (
            <Alert variant="success" title="Registration Successful" dismissible onClose={() => setSubmitSuccess(null)}>
              {submitSuccess}
            </Alert>
          )}

          {/* Registration Form */}
          {showForm && (
            <Card>
              <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-[#087F5B]" />
                Register New Ambulance
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Registration Number <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      name="registration_number"
                      value={form.registration_number}
                      onChange={handleChange}
                      placeholder="e.g. AMB-001"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Service Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      name="service_name"
                      value={form.service_name}
                      onChange={handleChange}
                      placeholder="e.g. City Emergency Services"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                    Device ID <span className="text-red-500">*</span>
                    <span className="ml-2 text-gray-400 normal-case font-normal">Unique hardware/device identifier</span>
                  </label>
                  <input
                    type="text"
                    name="device_id"
                    value={form.device_id}
                    onChange={handleChange}
                    placeholder="e.g. DEV-KHI-001"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    required
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Must be unique across the system. Duplicate device IDs are rejected.
                  </p>
                </div>

                {submitError && <Alert variant="error">{submitError}</Alert>}

                <div className="flex gap-3 pt-2">
                  <Button type="submit" loading={submitting} disabled={submitting}>
                    {submitting ? 'Registering…' : 'Register & Assign LifeLane ID'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => { setShowForm(false); setSubmitError(null); setForm(INITIAL_FORM); }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </Card>
          )}

          {/* Info box */}
          <Alert variant="info" title="LifeLane ID Assignment">
            Upon successful registration, the backend assigns a unique <strong>LifeLane ID</strong> (format: <code>LL-XXXXXXXX</code>). 
            This ID is permanent and links the ambulance to its device, emergency requests, and signal priority events.
          </Alert>

          {/* Error from listing */}
          {error && (
            <Alert variant="error" title="Failed to load ambulances">
              {error}
              <button onClick={refetch} className="ml-2 underline text-xs">Retry</button>
            </Alert>
          )}

          {/* Ambulance list */}
          <Card padding={false}>
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <div>
                <p className="section-eyebrow">Registry</p>
                <h2 className="mt-1 text-lg font-bold text-gray-900">Registered Ambulances</h2>
              </div>
              <span className="text-sm text-gray-500 font-semibold">{ambulances.length} total</span>
            </div>

            {loading ? (
              <div className="py-12"><LoadingSpinner /></div>
            ) : ambulances.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  icon={Ambulance}
                  title="No ambulances registered"
                  message='Use the "Register Ambulance" button to add the first ambulance and receive a LifeLane ID.'
                />
              </div>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left border-b border-gray-200 bg-gray-50">
                        {['LifeLane ID', 'Registration #', 'Service Name', 'Device ID', 'Status', 'Registered'].map((h) => (
                          <th key={h} className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {ambulances.map((amb) => (
                        <tr key={amb.id} className="hover:bg-gray-50 transition-colors">
                          <td className="py-3 px-4">
                            <CopyID id={amb.lifelane_id} />
                          </td>
                          <td className="py-3 px-4 font-medium text-gray-900">{amb.registration_number}</td>
                          <td className="py-3 px-4 text-gray-700">{amb.service_name}</td>
                          <td className="py-3 px-4 font-mono text-xs text-gray-500">{amb.device_id}</td>
                          <td className="py-3 px-4">
                            <Badge state={amb.status}>{amb.status}</Badge>
                          </td>
                          <td className="py-3 px-4 text-xs text-gray-400">{formatTimestamp(amb.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="md:hidden divide-y divide-gray-100">
                  {ambulances.map((amb) => (
                    <div key={amb.id} className="p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <CopyID id={amb.lifelane_id} />
                        <Badge state={amb.status}>{amb.status}</Badge>
                      </div>
                      <div className="text-sm font-semibold text-gray-900">{amb.registration_number}</div>
                      <div className="text-xs text-gray-500">{amb.service_name}</div>
                      <div className="text-xs font-mono text-gray-400">Device: {amb.device_id}</div>
                      <div className="text-xs text-gray-400">{formatTimestamp(amb.created_at)}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}
