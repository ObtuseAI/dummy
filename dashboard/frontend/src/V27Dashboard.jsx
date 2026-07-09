import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v27/mission-state'],
  ['Integration Mode Probes', '/api/v27/integration-mode-probes'],
  ['Public Probe Matrix', '/api/v27/public-probe-matrix'],
  ['Settlement Rule Library', '/api/v27/settlement-rule-library'],
  ['Kalshi Settlement Rules', '/api/v27/kalshi-settlement-rules'],
  ['Due Forecast Resolution', '/api/v27/due-forecast-resolution'],
  ['Weather Live Settlement', '/api/v27/weather-live-settlement'],
  ['Crypto Live Settlement', '/api/v27/crypto-live-settlement'],
  ['Commodity Macro Settlement', '/api/v27/commodity-macro-settlement'],
  ['Sports Terms', '/api/v27/sports-terms'],
  ['Sports Adapter Stub', '/api/v27/sports-adapter-stub'],
  ['Live Scoring Closure', '/api/v27/live-scoring-closure'],
  ['Live Calibration', '/api/v27/live-calibration'],
  ['Forecast Cadence', '/api/v27/forecast-cadence'],
  ['Observer Queue', '/api/v27/observer-queue'],
  ['Source Truth V9', '/api/v27/source-truth-v9'],
  ['Partial Reduction', '/api/v27/partial-reduction'],
  ['Adapter Sprint', '/api/v27/adapter-sprint'],
  ['Compounding V11', '/api/v27/compounding-v11'],
  ['Scoreboard V12', '/api/v27/scoreboard-v12'],
  ['Runtime Budget', '/api/v27/runtime-budget'],
  ['Safety', '/api/v27/safety'],
];

export default function V27Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v13 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Probes', mission.integration_probes_enabled_status || 'UNKNOWN'],
      ['Rules', mission.settlement_rule_library_status || 'UNKNOWN'],
      ['Due', mission.due_forecast_count ?? '0'],
      ['Observed', mission.observed_forecast_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Unresolved', mission.live_unresolved_count ?? '0'],
      ['Forecasts', mission.forecast_write_count ?? '0'],
      ['No-Trade', mission.no_trade_write_count ?? '0'],
      ['Sports', mission.sports_public_adapter_mode || 'UNKNOWN'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V27 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V27 Public Probe Closure</h1>
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
