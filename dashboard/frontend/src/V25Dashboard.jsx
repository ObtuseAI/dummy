import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v25/mission-state'],
  ['Market-Class Ontology', '/api/v25/market-class-ontology'],
  ['Market-Class Registry', '/api/v25/market-class-registry'],
  ['Evidence-to-Market Mapper', '/api/v25/evidence-to-market-mapper'],
  ['Settlement Mapping', '/api/v25/settlement-mapping'],
  ['Forecast Cadence', '/api/v25/forecast-cadence'],
  ['No-Trade Quality', '/api/v25/no-trade-quality'],
  ['Live Observer Loop', '/api/v25/live-observer-loop'],
  ['Market-Class Scoring', '/api/v25/market-class-scoring'],
  ['Replay Factory', '/api/v25/replay-factory'],
  ['Calibration V5', '/api/v25/calibration-v5'],
  ['Source Truth V7', '/api/v25/source-truth-v7'],
  ['Approved Market Discovery', '/api/v25/approved-market-class-discovery'],
  ['Source Stack Builder', '/api/v25/source-stack-builder'],
  ['Forecast Ledger', '/api/v25/forecast-ledger'],
  ['Adapter Acceleration', '/api/v25/adapter-acceleration'],
  ['Compounding V9', '/api/v25/compounding-v9'],
  ['Scoreboard V10', '/api/v25/scoreboard-v10'],
  ['Runtime Budget', '/api/v25/runtime-budget'],
  ['Safety', '/api/v25/safety'],
];

export default function V25Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v11 || {};
    const counts = mission.forecast_cadence_counts || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Classes', mission.market_class_families?.length ?? '0'],
      ['Forecasts', counts.forecast_count ?? '0'],
      ['No-Trade', counts.no_trade_count ?? '0'],
      ['Observers', counts.observer_count ?? '0'],
      ['Unresolved', mission.live_unresolved_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Replay', mission.replay_count ?? '0'],
      ['Replay Scores', mission.replay_scored_count ?? '0'],
      ['Source Truth', mission.source_truth_v7_status || 'UNKNOWN'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V25 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V25 Market-Class Intelligence</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
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
