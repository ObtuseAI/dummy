import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v33/mission-state'],
  ['Operator Run', '/api/v33/operator-enabled-probe-run'],
  ['Exact Ack', '/api/v33/exact-gate-ack'],
  ['Minimal Probe', '/api/v33/minimal-live-public-probe'],
  ['Weather', '/api/v33/weather-enabled-probe'],
  ['Crypto', '/api/v33/crypto-enabled-probe'],
  ['Public Event', '/api/v33/public-event-enabled-probe'],
  ['Kalshi Read-only', '/api/v33/kalshi-readonly-enabled-probe'],
  ['Live Evidence', '/api/v33/live-public-evidence'],
  ['Settlement Join', '/api/v33/settlement-evidence-join'],
  ['Due Observation', '/api/v33/due-forecast-observation'],
  ['Live Score', '/api/v33/live-score-observation'],
  ['Calibration', '/api/v33/live-calibration-observation'],
  ['Cache', '/api/v33/public-probe-cache'],
  ['Audit', '/api/v33/enabled-probe-audit'],
  ['Sports Exclusion', '/api/v33/sports-probe-exclusion'],
  ['Source Truth', '/api/v33/source-truth-v14'],
  ['Partial Reduction', '/api/v33/partial-reduction'],
  ['Sprint Queue', '/api/v33/probe-sprint-v10'],
  ['Compounding', '/api/v33/compounding-v17'],
  ['Scoreboard', '/api/v33/market-class-scoreboard'],
];

export default function V33Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v19 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.gate_state || 'UNKNOWN'],
      ['Ack', mission.exact_ack_validation_status || 'UNKNOWN'],
      ['Probe Runs', mission.probe_run_count ?? '0'],
      ['Families', mission.probe_source_family_count ?? '0'],
      ['Evidence', mission.live_public_evidence_packet_count ?? '0'],
      ['Settlement', mission.settlement_compatible_evidence_count ?? '0'],
      ['Observed', mission.observed_forecast_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Calibration', mission.live_calibration_observation_status || 'UNKNOWN'],
      ['Sports', mission.sports_source_mode || 'UNKNOWN'],
      ['Safety', mission.no_operator_enabled_probe_run_to_execution_bridge_status || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V33 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V33 Operator Public Probes</h1>
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
