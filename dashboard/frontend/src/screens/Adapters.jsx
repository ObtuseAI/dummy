import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Adapters() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/v3/adapters')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  const counts = data.counts || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Adapters</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Accepted" value={counts.accepted} />
        <Card label="Direct Dependency" value={counts.direct_dependency} />
        <Card label="Adapter Targets" value={counts.adapter_target} />
        <Card label="Reference Mines" value={counts.reference_mine} />
        <Card label="Rejected" value={counts.rejected} />
        <Card label="Pending Tests" value={(data.pending || []).length} />
      </div>

      <Section title={`Accepted Adapters (${(data.accepted || []).length})`}>
        {(data.accepted || []).length ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(data.accepted || []).map((a, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{a.adapter}</div>
                <div className="text-gray-400">{a.repo} &middot; {a.category}</div>
                <div className="text-xs mt-1 text-green-400">{a.verdict} &middot; emits_native_types: {String(a.emits_native_types)}</div>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">None</p>}
      </Section>

      <Section title={`Pending Tests (${(data.pending || []).length})`}>
        {(data.pending || []).length ? (
          <ul className="list-disc pl-5 text-sm space-y-1">
            {(data.pending || []).map((p, i) => <li key={i}>{typeof p === 'string' ? p : p.name || JSON.stringify(p)}</li>)}
          </ul>
        ) : <p className="text-sm text-gray-400">None pending</p>}
      </Section>

      <Section title={`Rejected Adapters (${(data.rejected || []).length})`}>
        {(data.rejected || []).length ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(data.rejected || []).map((r, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{r.repo}</div>
                <div className="text-gray-400">{r.category} &middot; {r.verdict}</div>
                {r.reasons?.length ? (
                  <ul className="list-disc pl-4 mt-1 text-xs text-red-400">
                    {r.reasons.map((reason, j) => <li key={j}>{reason}</li>)}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">None rejected</p>}
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
