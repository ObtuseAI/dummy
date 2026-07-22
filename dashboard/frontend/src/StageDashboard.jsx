import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

// Generic staged-gate dashboard. `endpoints` is [[title, path], ...]; `missionKey` is the
// mission report key inside the mission-state slice; `summaryFields` is [[label, key], ...].
export default function StageDashboard({ title, endpoints, missionKey, summaryFields }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const responses = await Promise.allSettled(endpoints.map(([, path]) => fetchJson(path)));
      setData(Object.fromEntries(endpoints.map(([t], i) => [
        t,
        responses[i].status === 'fulfilled'
          ? { value: responses[i].value, error: null }
          : { value: null, error: responses[i].reason?.message || 'Endpoint unavailable' },
      ])));
      setLoading(false);
    }
    load();
  }, []);

  const missionTitle = endpoints[endpoints.length - 1][0];
  const summary = useMemo(() => {
    const mission = data[missionTitle]?.value?.[missionKey] || {};
    return summaryFields.map(([label, key]) => [label, mission[key] === undefined ? 'UNKNOWN' : String(mission[key])]);
  }, [data]);

  if (loading) return <div className="p-4">Loading {title}...</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">{title}</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-base font-semibold text-white break-words">{value}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {endpoints.map(([t]) => (
          <div key={t} className="bg-gray-800 rounded p-4 border border-gray-700">
            <h2 className="text-base font-semibold mb-2">{t}</h2>
            {data[t]?.error ? (
              <div className="rounded border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
                Section unavailable: {data[t].error}
              </div>
            ) : (
              <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data[t]?.value, null, 2)}</pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
