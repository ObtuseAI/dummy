import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

// Generic staged-gate dashboard. `endpoints` is [[title, path], ...]; `missionKey` is the
// mission report key inside the mission-state slice; `summaryFields` is [[label, key], ...].
export default function StageDashboard({ title, endpoints, missionKey, summaryFields }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const responses = await Promise.all(endpoints.map(([, path]) => fetchJson(path)));
        setData(Object.fromEntries(endpoints.map(([t], i) => [t, responses[i]])));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const missionTitle = endpoints[endpoints.length - 1][0];
  const summary = useMemo(() => {
    const mission = data[missionTitle]?.[missionKey] || {};
    return summaryFields.map(([label, key]) => [label, mission[key] === undefined ? 'UNKNOWN' : String(mission[key])]);
  }, [data]);

  if (loading) return <div className="p-4">Loading {title}...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

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
            <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data[t], null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
