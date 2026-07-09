import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v26/mission-state'],
  ['Keyless Public Adapters', '/api/v26/keyless-public-adapters'],
  ['Keyless Probes', '/api/v26/keyless-probes'],
  ['Weather Settlement', '/api/v26/weather-settlement'],
  ['Crypto Settlement', '/api/v26/crypto-settlement'],
  ['Commodity Reference', '/api/v26/commodity-reference'],
  ['Finance Macro Events', '/api/v26/finance-macro-events'],
  ['Sports Schedule Status', '/api/v26/sports-schedule-status'],
  ['Public Events', '/api/v26/public-events'],
  ['Kalshi Readonly Join', '/api/v26/kalshi-readonly-join'],
  ['Settlement Closure', '/api/v26/settlement-closure'],
  ['Forecast Resolution', '/api/v26/forecast-resolution'],
  ['Forecast Cadence', '/api/v26/forecast-cadence'],
  ['Live Scoring Closure', '/api/v26/live-scoring-closure'],
  ['Replay To Live', '/api/v26/replay-to-live'],
  ['Source Truth V8', '/api/v26/source-truth-v8'],
  ['Adapter Sprint', '/api/v26/adapter-sprint'],
  ['Compounding V10', '/api/v26/compounding-v10'],
  ['Scoreboard V11', '/api/v26/scoreboard-v11'],
  ['Runtime Budget', '/api/v26/runtime-budget'],
  ['Safety', '/api/v26/safety'],
];

export default function V26Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v12 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Adapters', mission.keyless_adapter_active_count ?? '0'],
      ['Forecasts', mission.forecast_write_count ?? '0'],
      ['No-Trade', mission.no_trade_write_count ?? '0'],
      ['Observers', mission.observer_queue_count ?? '0'],
      ['Due', mission.due_forecast_count ?? '0'],
      ['Observed', mission.observed_forecast_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Unresolved', mission.live_unresolved_count ?? '0'],
      ['Replay Scores', mission.replay_scored_count ?? '0'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V26 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V26 Keyless Settlement</h1>
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
