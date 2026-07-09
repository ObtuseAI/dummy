import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function V7Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [identity, routerStatus, opinion, intel, rehearsal, reports] = await Promise.all([
          fetchJson('/v7/identity'),
          fetchJson('/v7/model-router/status'),
          fetchJson('/v7/forecast/opinion'),
          fetchJson('/v7/strategies/intelligence'),
          fetchJson('/v7/hybrid/rehearsal'),
          fetchJson('/v7/reports/status'),
        ]);
        setData({ identity, routerStatus, opinion, intel, rehearsal, reports });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="p-4">Loading V7 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Dummy V7 Dashboard</h1>
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="bg-gray-800 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">{key}</h2>
          <pre className="text-sm overflow-auto max-h-64 bg-gray-900 p-2 rounded">{JSON.stringify(value, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
