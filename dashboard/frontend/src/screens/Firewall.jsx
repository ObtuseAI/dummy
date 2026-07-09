import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Firewall() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/v3/firewall/verdicts')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Firewall Verdicts</h1>

      <Card label="Recent Verdicts" value={data.count || 0} />

      <Section title={`Verdicts (${(data.verdicts || []).length})`}>
        {(data.verdicts || []).length ? (
          <div className="space-y-2 max-h-[32rem] overflow-y-auto">
            {(data.verdicts || []).map((v, i) => (
              <div key={i} className={`bg-gray-900 p-3 rounded text-sm border-l-4 ${v.allow ? 'border-green-500' : 'border-red-500'}`}>
                <div className="flex justify-between">
                  <span className="text-gray-400 text-xs">{v.timestamp}</span>
                  <span className={`text-xs font-bold ${v.allow ? 'text-green-400' : 'text-red-400'}`}>
                    {v.allow ? 'ALLOW' : 'REJECT'}
                  </span>
                </div>
                <div className="mt-1 font-semibold">{v.level?.toUpperCase()}</div>
                <div>{v.message}</div>
                {v.rejected_by ? <div className="text-xs text-gray-400">Rejected by: {v.rejected_by}</div> : null}
                {v.proposal_id ? <div className="text-xs text-gray-400">Proposal: {v.proposal_id}</div> : null}
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No firewall verdicts recorded</p>}
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
