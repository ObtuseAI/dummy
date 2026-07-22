import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

export default function BlockedOrders() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/api/read-only/firewall/rejections').then(setData).catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Blocked-order evidence unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading local rejection evidence…</div>;
  const reasons = Array.isArray(data.observed_reasons) ? data.observed_reasons : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Blocked-order evidence</h1>
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        Counts come from structured reasons in the last 1,000 local log lines. They are not a lifetime total and do not imply broker contact.
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Card label="Observed rejections" value={data.observed_rejection_count} />
        <Card label="Firewall events scanned" value={data.firewall_events_scanned} />
        <Card label="Source" value={data.source} />
      </div>
      <div className="rounded bg-gray-800 p-4">
        <h2 className="mb-3 text-lg font-semibold">Reasons ({reasons === null ? 'UNKNOWN' : reasons.length})</h2>
        {reasons === null ? (
          <p className="text-sm font-semibold text-amber-300">UNKNOWN — local rejection evidence unavailable.</p>
        ) : reasons.length ? reasons.map(item => (
          <div key={item.reason} className="mb-2 flex justify-between rounded bg-gray-900 p-3 text-sm">
            <span>{valueOrUnknown(item.reason)}</span><span className="font-mono">{valueOrUnknown(item.count)}</span>
          </div>
        )) : <p className="text-sm text-gray-400">No structured rejection reason was observed in this bounded window.</p>}
      </div>
    </div>
  );
}

function Card({ label, value }) {
  return <div className="rounded bg-gray-800 p-4"><div className="text-sm text-gray-400">{label}</div><div className="break-words text-xl font-bold">{String(valueOrUnknown(value))}</div></div>;
}
