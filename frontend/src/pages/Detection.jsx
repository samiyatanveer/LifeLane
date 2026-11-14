import { useState, useCallback } from 'react';
import { Menu, Upload, X, Mic } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Alert from '../components/ui/Alert';
import SimulationBadge from '../components/ui/SimulationBadge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ThemeToggle from '../components/ui/ThemeToggle';
import { postDetection } from '../api/detection';
import { useDetections } from '../hooks/useDetections';
import { formatTimestamp, formatConfidence, formatFileSize } from '../utils/format';
import { APPROACHES, JUNCTIONS, ACCEPTED_AUDIO_TYPES, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB } from '../utils/constants';

const ITEMS_PER_PAGE = 10;

function DropZone({ file, onFile, onClear }) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (f) onFile(f);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
        ${dragging ? 'border-[#087F5B] bg-green-50' : 'border-gray-300 hover:border-[#087F5B] hover:bg-gray-50'}`}
    >
      <input
        id="audio-file"
        type="file"
        accept={ACCEPTED_AUDIO_TYPES.join(',')}
        className="absolute inset-0 opacity-0 cursor-pointer"
        onChange={handleChange}
      />
      {file ? (
        <div className="flex items-center justify-center gap-3">
          <Mic className="w-6 h-6 text-[#087F5B]" />
          <div className="text-left">
            <p className="font-medium text-gray-900 text-sm truncate max-w-xs">{file.name}</p>
            <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
          </div>
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClear(); }}
            className="ml-2 p-1 rounded-full hover:bg-gray-200 text-gray-500"
            aria-label="Clear file"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div>
          <Upload className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-600">Drag & drop audio file here</p>
          <p className="text-xs text-gray-400 mt-1">or <span className="text-[#087F5B] underline">click to browse</span></p>
          <p className="text-xs text-gray-400 mt-2">{ACCEPTED_AUDIO_TYPES.join(', ')} · Max {MAX_FILE_SIZE_MB}MB</p>
        </div>
      )}
    </div>
  );
}

function ConfidenceBar({ value, isSiren }) {
  const pct = Math.round((value || 0) * 100);
  const color = isSiren ? 'bg-red-500' : 'bg-green-500';
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Confidence</span>
        <span className="font-semibold">{pct}%</span>
      </div>
      <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function Detection() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [approach, setApproach] = useState('north');
  const [junction, setJunction] = useState('J1');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);

  const { detections, loading: histLoading, refetch } = useDetections(20, null);

  const handleFile = (f) => {
    if (f.size > MAX_FILE_SIZE_BYTES) {
      setError(`File too large (max ${MAX_FILE_SIZE_MB}MB)`);
      return;
    }
    setFile(f);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select an audio file'); return; }
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await postDetection(file, approach, junction);
      setResult(res);
      refetch();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(detections.length / ITEMS_PER_PAGE));
  const pagedDetections = detections.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  return (
    <div className="ops-page min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        <header className="ops-header sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button className="lg:hidden p-2 rounded-md hover:bg-gray-100" onClick={() => setMobileOpen(true)}>
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <Mic className="w-5 h-5 text-[#087F5B]" />
          <h1 className="font-bold text-gray-900 text-lg flex-1">Audio Detection</h1>
          <SimulationBadge />
          <ThemeToggle />
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">
          {/* Upload form */}
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">Analyze Audio File</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <DropZone file={file} onFile={handleFile} onClear={() => setFile(null)} />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                    Approach Direction
                  </label>
                  <select
                    value={approach}
                    onChange={(e) => setApproach(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                  >
                    {APPROACHES.map((a) => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                    Junction
                  </label>
                  <select
                    value={junction}
                    onChange={(e) => setJunction(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                  >
                    {JUNCTIONS.map((j) => (
                      <option key={j.id} value={j.id}>{j.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {error && <Alert variant="error">{error}</Alert>}

              <Button type="submit" disabled={!file || loading} loading={loading} className="w-full sm:w-auto">
                {loading ? 'Analyzing…' : 'Analyze Audio'}
              </Button>
            </form>
          </Card>

          {/* Loading state */}
          {loading && (
            <Card className="flex flex-col items-center py-8 gap-3">
              <LoadingSpinner size="lg" />
              <div className="text-center">
                <p className="font-medium text-gray-700">Processing audio…</p>
                <p className="text-sm text-gray-400">Extracting embeddings and running classifier</p>
              </div>
            </Card>
          )}

          {/* Result card */}
          {result && !loading && (
            <Card>
              <div className="text-center mb-4">
                <div className={`text-3xl font-extrabold mb-2 ${result.is_siren ? 'text-red-600' : 'text-green-700'}`}>
                  {result.is_siren ? '🚨 SIREN DETECTED' : '✓ NO SIREN'}
                </div>
                <ConfidenceBar value={result.confidence} isSiren={result.is_siren} />
              </div>
              <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wide block mb-0.5">Model</span>
                  <Badge state={result.model_type?.split('_')[0]}>{result.model_type}</Badge>
                </div>
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wide block mb-0.5">Threshold</span>
                  <span className="font-medium">{result.threshold ?? '—'}</span>
                </div>
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wide block mb-0.5">Junction</span>
                  <span className="font-medium">{result.junction_id ?? junction}</span>
                </div>
              </div>
              {result.warning && (
                <Alert variant="warning" className="mt-4">
                  <strong>⚠ Warning:</strong> {result.warning}
                </Alert>
              )}
            </Card>
          )}

          {/* Info box */}
          <Alert variant="info" title="What This Means">
            Audio detection alone <strong>never</strong> grants signal priority. A detected siren is only the first
            of three verification steps. Identity confirmation and an active emergency request are also required
            before the SUMO simulation changes any signal state.
          </Alert>

          {/* Detection history */}
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">Detection History (Last 20)</h2>
            {histLoading ? (
              <LoadingSpinner />
            ) : detections.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">No detections recorded yet</p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left border-b border-gray-200">
                        {['Time', 'Junction', 'Approach', 'Result', 'Confidence', 'Model'].map((h) => (
                          <th key={h} className="pb-2 pr-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {pagedDetections.map((d, i) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="py-2.5 pr-4 text-xs text-gray-500">{formatTimestamp(d.created_at || d.timestamp)}</td>
                          <td className="py-2.5 pr-4 font-medium">{d.junction_id || '—'}</td>
                          <td className="py-2.5 pr-4 capitalize">{d.approach || '—'}</td>
                          <td className="py-2.5 pr-4">
                            <span className={`font-semibold ${d.is_siren ? 'text-red-600' : 'text-green-700'}`}>
                              {d.is_siren ? 'SIREN' : 'No Siren'}
                            </span>
                          </td>
                          <td className="py-2.5 pr-4">{formatConfidence(d.confidence)}</td>
                          <td className="py-2.5">
                            <Badge state={d.model_type?.split('_')[0]}>{d.model_type}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="md:hidden space-y-3">
                  {pagedDetections.map((d, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-3 text-sm">
                      <div className="flex justify-between mb-1">
                        <span className={`font-bold ${d.is_siren ? 'text-red-600' : 'text-green-700'}`}>
                          {d.is_siren ? 'SIREN' : 'No Siren'}
                        </span>
                        <span className="text-xs text-gray-500">{formatTimestamp(d.created_at)}</span>
                      </div>
                      <div className="text-xs text-gray-500 flex gap-3">
                        <span>{d.junction_id}</span>
                        <span className="capitalize">{d.approach}</span>
                        <span>{formatConfidence(d.confidence)}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4 text-sm">
                    <span className="text-gray-500">Page {page} of {totalPages}</span>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
                      <Button variant="secondary" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}
