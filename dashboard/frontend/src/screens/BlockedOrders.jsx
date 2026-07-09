import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function BlockedOrders() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/v3/blocked-orders')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Blocked Orders</h1>

      <div className="grid grid-cols-3 gap-4">
        <Card label="Static Reasons" value={(data.static_reasons || []).length} />
        <Card label="Recent Firewall Rejections" value={(data.recent_firewall_rejections || []).length} />
        <Card label="Total Blocked" value={data.count || 0} />
      </div>

      <Section title={`Static Reasons (${(data.static_reasons || []).length})`}>
        {(data.static_reasons || []).length ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(data.static_reasons || []).map((r, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{r.repo}</div>
                <div className="text-red-400">{r.category}</div>
                {r.details?.length ? (
                  <ul className="list-disc pl-4 mt-1 text-xs text-gray-400">
                    {r.details.map((d, j) => <li key={j}>{typeof d === 'string' ? d : JSON.stringify(d)}</li>)}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No static reasons</p>}
      </Section>

      <Section title={`Recent Firewall Rejections (${(data.recent_firewall_rejections || []).length})`}>
        {(data.recent_firewall_rejections || []).length ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(data.recent_firewall_rejections || []).map((r, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="text-gray-400 text-xs">{r.timestamp}</div>
                <div className="font-semibold">{r.category}</div>
                <div>{r.reason}</div>
                {r.proposal_id ? <div className="text-xs text-gray-400">Proposal: {r.proposal_id}</div> : null}
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No recent firewall rejections</p>}
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(value ?? 0)}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}
