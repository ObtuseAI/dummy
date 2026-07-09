import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function StrategyCandidates() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/v3/strategies/candidates')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Strategy Candidates</h1>

      <Section title="Registered Dummy Strategies">
        <div className="flex flex-wrap gap-2">
          {(data.registered_strategies || []).map(name => (
            <span key={name} className="px-2 py-1 bg-blue-900 rounded text-sm">{name}</span>
          ))}
        </div>
      </Section>

      <Section title={`Repo-Derived Candidates (${data.candidate_count || 0})`}>
        {(data.candidates || []).length ? (
          <div className="space-y-3 max-h-[32rem] overflow-y-auto">
            {(data.candidates || []).map((c, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{c.strategy_name}</div>
                <div className="text-gray-400">Source: {c.repo} ({c.source_category})</div>
                <div className="mt-1">{c.description}</div>
                <div className="mt-1 text-xs text-green-400">Output: {c.output} &middot; live_order_endpoints: {String(c.calls_live_order_endpoints)}</div>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No candidates</p>}
      </Section>
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
