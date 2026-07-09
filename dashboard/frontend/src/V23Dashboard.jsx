import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v23/mission-state'],
  ['Forecast Observer Closure', '/api/v23/forecast-observer-closure'],
  ['Crypto Outcome Observer', '/api/v23/crypto-outcome-observer'],
  ['Weather Outcome Observer', '/api/v23/weather-outcome-observer'],
  ['Forecast Scoring V2', '/api/v23/forecast-scoring'],
  ['Calibration Update V3', '/api/v23/calibration-update'],
  ['Forecast Attribution V2', '/api/v23/forecast-attribution'],
  ['Source Truth Score V4', '/api/v23/source-truth-score'],
  ['Tier-0 Adapter Closure', '/api/v23/tier0-adapter-closure'],
  ['CME Adapter Gate', '/api/v23/cme-adapter-gate'],
  ['Databento Adapter Gate', '/api/v23/databento-adapter-gate'],
  ['EIA Activation Closure', '/api/v23/eia-activation-closure'],
  ['Rates/DXY Context', '/api/v23/rates-dxy-context'],
  ['Nasdaq/Oil Readiness', '/api/v23/nasdaq-oil-readiness'],
  ['Forecast Lifecycle', '/api/v23/forecast-lifecycle'],
  ['Compounding V6', '/api/v23/compounding-v6'],
  ['Domain Scoreboard V7', '/api/v23/domain-scoreboard-v7'],
];

export default function V23Dashboard() {
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
      ['Snapshots', mission.v22_forecast_snapshots ?? '0'],
      ['Observed', mission.observed_outcome_count ?? '0'],
      ['Scored', mission.scored_forecast_count ?? '0'],
      ['Unresolved', mission.unresolved_forecast_count ?? '0'],
      ['CME', mission.cme_gate_status || 'UNKNOWN'],
      ['Databento', mission.databento_gate_status || 'UNKNOWN'],
      ['EIA', mission.eia_closure_status || 'UNKNOWN'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V23 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V23 Observer Calibration</h1>
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
