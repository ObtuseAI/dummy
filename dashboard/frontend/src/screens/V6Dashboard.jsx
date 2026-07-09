import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function V6Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [identity, status, audit, scan, firewall, caps, liveSubmit] = await Promise.all([
          fetchJson('/v6/identity'),
          fetchJson('/v6/kalshi/status'),
          fetchJson('/v6/endpoint-audit'),
          fetchJson('/v6/strategies/scan'),
          fetchJson('/v6/firewall/rehearse'),
          fetchJson('/v6/caps'),
          fetchJson('/v6/live-submit/status'),
        ]);
        setData({ identity, status, audit, scan, firewall, caps, liveSubmit });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="p-4">Loading V6 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Dummy V6 Dashboard</h1>
      <Section title="Identity" data={data.identity} />
      <Section title="Kalshi Status" data={data.status} />
      <Section title="Endpoint Audit" data={data.audit} />
      <Section title="Strategy Scan" data={data.scan} />
      <Section title="Firewall Rehearsal" data={data.firewall} />
      <Section title="Caps" data={data.caps} />
      <Section title="Live-Submit Status" data={data.liveSubmit} />
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <pre className="text-sm overflow-auto max-h-64 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
