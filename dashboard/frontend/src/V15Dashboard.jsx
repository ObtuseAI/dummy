import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Credential Shape Repair', '/api/v15/credential-shape-repair'],
  ['Credential Source Conflicts', '/api/v15/credential-source-conflicts'],
  ['Normalization Preview', '/api/v15/normalization-preview'],
  ['Auth Probe V2', '/api/v15/auth-probe-v2'],
  ['Real Terrain Retry V2', '/api/v15/real-terrain-retry-v2'],
  ['Real Orderbook Terrain V3', '/api/v15/real-orderbook-terrain-v3'],
  ['Liquidity Launch Gate V2', '/api/v15/liquidity-launch-gate-v2'],
  ['Source Adapter Closure V5', '/api/v15/source-adapter-closure-v5'],
  ['Runtime Acceleration V2', '/api/v15/runtime-acceleration-v2'],
];

export default function V15Dashboard() {
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
    const shape = data['Credential Shape Repair']?.shape_repair || {};
    const conflicts = data['Credential Source Conflicts']?.conflict_resolution || {};
    const auth = data['Auth Probe V2']?.auth_probe?.outcome || {};
    const retry = data['Real Terrain Retry V2']?.retry_gate || {};
    const terrain = data['Real Orderbook Terrain V3']?.terrain || {};
    const launch = data['Liquidity Launch Gate V2']?.matrix || {};
    const source = data['Source Adapter Closure V5']?.closure || {};
    const runtime = data['Runtime Acceleration V2']?.runtime_acceleration || {};
    return [
      ['Shape', shape.verdict_state || 'UNKNOWN'],
      ['Conflicts', conflicts.has_conflict ? 'CONFLICT' : 'CLEAN'],
      ['Auth', auth.decision || 'UNKNOWN'],
      ['Retry', retry.decision || 'UNKNOWN'],
      ['Terrain', terrain.terrain_mode || 'UNKNOWN'],
      ['Launch Gate', launch.gate_output || 'UNKNOWN'],
      ['Source', source.kalshi_terrain_mode || 'UNKNOWN'],
      ['Submit', data['Runtime Acceleration V2']?.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Runtime', runtime.verdict || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V15 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V15 Dashboard</h1>
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
