import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v22/mission-state'],
  ['Edge Role Classifier', '/api/v22/edge-role-classifier'],
  ['Evidence Normalizer', '/api/v22/evidence-normalizer'],
  ['Crypto Spot Edge', '/api/v22/crypto-spot-edge'],
  ['Weather Edge', '/api/v22/weather-edge'],
  ['Commodity Guard', '/api/v22/commodity-context-guard'],
  ['Finance Guard', '/api/v22/finance-context-guard'],
  ['Market Mapper', '/api/v22/market-event-mapper'],
  ['Kalshi Mapping', '/api/v22/kalshi-market-mapping'],
  ['Forecast Writes', '/api/v22/forecast-write-breakthrough'],
  ['Observer Queue', '/api/v22/outcome-observer-queue'],
  ['Ledger Writes', '/api/v22/ledger-writes'],
  ['Edge Source Acquisition', '/api/v22/edge-source-acquisition'],
  ['GitHub Adapter Queue', '/api/v22/github-adapter-queue'],
  ['Compounding V5', '/api/v22/compounding-v5'],
  ['Domain Scoreboard V6', '/api/v22/domain-scoreboard-v6'],
];

export default function V22Dashboard() {
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
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Real Sources', mission.active_real_source_count ?? '0'],
      ['Edge', mission.context_vs_edge_split?.edge ?? '0'],
      ['Context', mission.context_vs_edge_split?.context ?? '0'],
      ['Forecasts', mission.forecast_snapshot_count ?? '0'],
      ['No-Trade', mission.no_trade_count ?? '0'],
      ['Observer', mission.observer_queue_count ?? '0'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V22 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V22 Edge Activation</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
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
