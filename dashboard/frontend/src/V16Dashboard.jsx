import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v16/mission-state'],
  ['Real Terrain Truth', '/api/v16/real-terrain-truth'],
  ['Config Binding', '/api/v16/config-binding'],
  ['Proof Freshness', '/api/v16/proof-freshness'],
];

export default function V16Dashboard() {
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
    const mission = data['Mission State']?.mission_state || {};
    const truth = data['Real Terrain Truth']?.terrain_truth || {};
    const binding = data['Config Binding']?.config_binding || {};
    const freshness = data['Proof Freshness']?.proof_freshness || {};
    return [
      ['Mission', mission.mission_state_verdict || 'UNKNOWN'],
      ['Shape', mission.credential_shape || 'UNKNOWN'],
      ['Auth', mission.auth_probe || 'UNKNOWN'],
      ['Binding', binding.binding_state || 'UNKNOWN'],
      ['Discovery', mission.market_discovery || 'UNKNOWN'],
      ['Snapshot', mission.orderbook_snapshot || 'UNKNOWN'],
      ['Terrain', truth.terrain_truth_verdict || mission.terrain_truth_verdict || 'UNKNOWN'],
      ['Replay', mission.replay_mode || 'UNKNOWN'],
      ['Freshness', freshness.freshness_state || 'UNKNOWN'],
      ['Submit', mission.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'CHECK'],
      ['Bypass', mission.no_direct_order_cancel_bypass ? 'CLEAR' : 'CHECK'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V16 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V16 Mission State</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
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
