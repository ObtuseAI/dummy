import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Kalshi Forensics', '/api/v14/kalshi-forensics'],
  ['Repair Wizard', '/api/v14/kalshi-repair-wizard'],
  ['Real Terrain Retry', '/api/v14/real-terrain-retry'],
  ['Real Terrain Closure', '/api/v14/real-terrain-closure'],
  ['Source Adapter Promotion', '/api/v14/source-adapter-promotion'],
  ['Launch Readiness', '/api/v14/liquidity-launch-readiness'],
  ['Micro Order Dry Run', '/api/v14/micro-order-dry-run'],
  ['No Trade Gates', '/api/v14/liquidity-no-trade-gates'],
  ['Runtime Acceleration', '/api/v14/runtime-acceleration'],
];

export default function V14Dashboard() {
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
    const forensics = data['Kalshi Forensics']?.forensics || {};
    const retry = data['Real Terrain Retry']?.retry_gate || {};
    const terrainClosure = data['Real Terrain Closure'] || {};
    const closure = terrainClosure.snapshot || {};
    const source = data['Source Adapter Promotion']?.promotion || {};
    const launch = data['Launch Readiness']?.matrix || {};
    const micro = data['Micro Order Dry Run']?.packet || {};
    const runtime = data['Runtime Acceleration']?.runtime_acceleration || {};
    return [
      ['Credentials', forensics.failure_reason || 'UNKNOWN'],
      ['Retry', retry.decision || 'UNKNOWN'],
      ['Snapshot', closure.snapshot_mode || 'UNKNOWN'],
      ['Terrain', closure.terrain_mode || 'UNKNOWN'],
      ['Source', source.kalshi_orderbook_liquidity_mode || 'UNKNOWN'],
      ['Launch', launch.gate_output || 'UNKNOWN'],
      ['Dry Run', micro.verdict || 'UNKNOWN'],
      ['Submit', terrainClosure.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Runtime', runtime.verdict || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V14 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V14 Dashboard</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-9">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-base font-semibold text-white break-words">{String(value)}</div>
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
