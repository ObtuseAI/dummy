import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Real Orderbook Snapshot', '/api/v12/orderbook-snapshot'],
  ['Liquidity Replay', '/api/v12/liquidity-replay'],
  ['Real-Terrain Liquidity Proof', '/api/v12/liquidity-proof-v2'],
  ['Fill Quality V2', '/api/v12/fill-quality-v2'],
  ['Stale Quote Risk V2', '/api/v12/stale-quote-risk-v2'],
  ['Liquidity Calibration Store', '/api/v12/liquidity-calibration'],
  ['Source Adapter Closure', '/api/v12/source-adapter-closure'],
  ['Liquidity Bloodlines', '/api/v12/liquidity-bloodlines'],
];

export default function V12Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const responses = await Promise.all(endpoints.map(([, path]) => fetchJson(path)));
        setData(Object.fromEntries(endpoints.map(([title], index) => [title, responses[index]])));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const summary = useMemo(() => {
    const snapshot = data['Real Orderbook Snapshot'] || {};
    const replay = data['Liquidity Replay'] || {};
    const proof = data['Real-Terrain Liquidity Proof'] || {};
    const fill = data['Fill Quality V2'] || {};
    const closure = data['Source Adapter Closure'] || {};
    const bloodlines = data['Liquidity Bloodlines'] || {};
    return [
      ['Snapshot', snapshot.snapshot_mode || 'UNKNOWN'],
      ['Terrain', snapshot.real_vs_fallback_status || 'UNKNOWN'],
      ['Replay', replay.verdict || 'UNKNOWN'],
      ['Proof', proof.verdict || 'UNKNOWN'],
      ['Fill Drag', fill.estimate?.fill_drag?.drag_cents ?? 'UNKNOWN'],
      ['Submit', snapshot.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Closure', closure.verdict || 'UNKNOWN'],
      ['Bloodlines', bloodlines.verdict || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V12 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V12 Dashboard</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-lg font-semibold text-white break-words">{String(value)}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {endpoints.map(([title]) => (
          <Section key={title} title={title} data={data[title]} />
        ))}
      </div>
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4 border border-gray-700">
      <h2 className="text-base font-semibold mb-2">{title}</h2>
      <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
