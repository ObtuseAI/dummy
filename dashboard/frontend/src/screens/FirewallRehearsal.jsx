import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function FirewallRehearsal() {
  const [data, setData] = useState(null);
  const [blocked, setBlocked] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/api/read-only/firewall/rehearsal')
      .then(setData)
      .catch(e => setError(e.message));
    fetchJson('/api/read-only/firewall/rejections')
      .then(setBlocked)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Firewall Rehearsal</h1>
      <div className="rounded border-2 border-cyan-700 bg-cyan-950/40 p-4 text-sm text-cyan-100">
        This production page is read-only. It reports whether a rehearsal was recorded; loading the page never executes the firewall or contacts a broker.
      </div>

      {data ? (
        <div className="bg-gray-800 rounded p-4">
          <div className="flex gap-4 mb-4">
            <Card label="Status" value={data.status} />
            <Card label="Rehearsal Executed" value={booleanLabel(data.rehearsal_executed)} />
            <Card label="Live Submitted" value={booleanLabel(data.live_submitted)} />
            <Card label="Credentials Present" value={booleanLabel(data.credentials_present)} />
          </div>
          {data.rehearsal_executed === false && (
            <div className="mb-4 rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
              NOT EXECUTED — {valueOrUnknown(data.reason)}
            </div>
          )}
          {data.rehearsal_executed == null && (
            <div className="mb-4 rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
              REHEARSAL EXECUTION STATUS UNKNOWN — no result may be inferred.
            </div>
          )}
          {data.firewall_rehearsal && (
            <div className="mb-4 p-3 bg-gray-900 rounded text-sm">
              <div>Would submit: {booleanLabel(data.firewall_rehearsal.would_submit)}</div>
              <div>Blocked reason: {valueOrUnknown(data.firewall_rehearsal.blocked_reason)}</div>
              <div>Firewall allow: {booleanLabel(data.firewall_rehearsal.firewall_verdict?.allow)}</div>
              {data.firewall_rehearsal.order && (
                <pre className="mt-2 text-xs">{JSON.stringify(data.firewall_rehearsal.order, null, 2)}</pre>
              )}
            </div>
          )}
          <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto max-h-96">{JSON.stringify(data, null, 2)}</pre>
        </div>
      ) : (
        <p className="text-sm text-gray-400">Loading...</p>
      )}

      {blocked && (
        <div className="bg-gray-800 rounded p-4">
          <h2 className="text-lg font-semibold mb-1">Observed Firewall Rejections</h2>
          <p className="mb-3 text-xs text-gray-400">Log-derived from {valueOrUnknown(blocked.window)}; source: {valueOrUnknown(blocked.source)}</p>
          {!Array.isArray(blocked.observed_reasons) ? (
            <p className="text-sm font-semibold text-amber-300">Rejection evidence: UNKNOWN — local log unavailable.</p>
          ) : blocked.observed_reasons.length ? (
            <div className="space-y-2">
              {blocked.observed_reasons.map(item => (
                <div key={item.reason} className="flex justify-between rounded bg-gray-900 px-3 py-2 text-sm">
                  <span>{valueOrUnknown(item.reason)}</span><span className="font-mono">{valueOrUnknown(item.count)}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-gray-400">No structured firewall rejection reasons observed in this window.</p>}
        </div>
      )}
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-3 bg-gray-900 rounded">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-lg font-bold">{String(valueOrUnknown(value))}</div>
    </div>
  );
}
