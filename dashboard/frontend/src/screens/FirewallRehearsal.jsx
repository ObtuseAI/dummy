import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function FirewallRehearsal() {
  const [data, setData] = useState(null);
  const [blocked, setBlocked] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v4/firewall/rehearse')
      .then(setData)
      .catch(e => setError(e.message));
    fetchJson('/v4/firewall/blocked')
      .then(setBlocked)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Firewall Rehearsal</h1>

      {data ? (
        <div className="bg-gray-800 rounded p-4">
          <div className="flex gap-4 mb-4">
            <Card label="Status" value={data.status} />
            <Card label="Live Submitted" value={data.live_submitted ? 'Yes' : 'No'} />
            <Card label="Credentials Present" value={data.credentials_present ? 'Yes' : 'No'} />
          </div>
          {data.firewall_rehearsal && (
            <div className="mb-4 p-3 bg-gray-900 rounded text-sm">
              <div>Would submit: {data.firewall_rehearsal.would_submit ? 'Yes' : 'No'}</div>
              <div>Blocked reason: {data.firewall_rehearsal.blocked_reason || 'none'}</div>
              <div>Firewall allow: {data.firewall_rehearsal.firewall_verdict?.allow ? 'Yes' : 'No'}</div>
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
          <h2 className="text-lg font-semibold mb-3">Blocked Order Reasons</h2>
          <div className="flex flex-wrap gap-2">
            {(blocked.blocked_reasons || []).map((reason, i) => (
              <span key={i} className="px-2 py-1 bg-gray-900 rounded text-xs">{reason}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-3 bg-gray-900 rounded">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-lg font-bold">{String(value ?? '—')}</div>
    </div>
  );
}
