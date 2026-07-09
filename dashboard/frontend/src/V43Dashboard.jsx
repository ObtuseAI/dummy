import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Developing Sample Controller', '/api/v43/developing-sample-controller'],
  ['Exact Gate V11', '/api/v43/exact-gate'],
  ['V42 Baseline', '/api/v43/v42-baseline'],
  ['Sample Extension', '/api/v43/sample-extension'],
  ['Sample Quality', '/api/v43/sample-quality'],
  ['Tier Governor', '/api/v43/tier-governor'],
  ['Calibration Stability', '/api/v43/calibration-stability'],
  ['Source Truth V24', '/api/v43/source-truth-v24'],
  ['Market-Class Reliability', '/api/v43/market-class-reliability'],
  ['No-Trade Trend', '/api/v43/no-trade-trend'],
  ['Forecast Quality Trend', '/api/v43/forecast-quality-trend'],
  ['Observer Scaleout', '/api/v43/observer-scaleout'],
  ['Readiness Governor', '/api/v43/readiness-governor'],
  ['Execution Lock', '/api/v43/execution-lock'],
  ['Next Action', '/api/v43/next-action'],
  ['Audit Ledger', '/api/v43/audit-ledger'],
  ['Mission State V43', '/api/v43/mission-state'],
];

export default function V43Dashboard() {
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
    const mission = data['Mission State V43']?.dummy_mission_state_report_v29 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V42 Baseline', mission.v42_baseline_status || 'UNKNOWN'],
      ['V42 Scores', mission.v42_cumulative_real_scored_count ?? 0],
      ['V43 Extension', mission.optional_developing_sample_extension_status || 'UNKNOWN'],
      ['V43 Probes', mission.v43_new_real_probe_count ?? 0],
      ['V43 Evidence', mission.v43_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v43_duplicate_stale_excluded_count ?? 0],
      ['V43 Settlement', mission.v43_new_settlement_compatible_count ?? 0],
      ['V43 Observed', mission.v43_new_observed_count ?? 0],
      ['V43 Scores', mission.v43_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Sample Quality', mission.sample_quality_status || 'UNKNOWN'],
      ['Threshold', mission.developing_sample_threshold_decision || 'UNKNOWN'],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Calibration Stability', mission.calibration_stability_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v24_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v4_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v4_status || 'UNKNOWN'],
      ['Forecast Trend', mission.forecast_quality_ledger_v2_status || 'UNKNOWN'],
      ['Observer Scaleout', mission.observer_scaleout_plan_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v3_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v2_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V43 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V43 Developing Sample Observer Scaleout</h1>
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
