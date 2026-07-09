import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Stable Sample Threshold Controller', '/api/v47/stable-sample-threshold-controller'],
  ['Exact Gate V15', '/api/v47/exact-gate'],
  ['V46 Baseline', '/api/v47/v46-baseline'],
  ['Observer Threshold Closure', '/api/v47/observer-threshold-closure'],
  ['Stable Sample Gate', '/api/v47/stable-sample-gate'],
  ['Drift Reliability', '/api/v47/drift-reliability'],
  ['Source Truth V28', '/api/v47/source-truth'],
  ['Market-Class Reliability V8', '/api/v47/market-class-reliability'],
  ['No-Trade V8', '/api/v47/no-trade'],
  ['Forecast Quality V6', '/api/v47/forecast-quality'],
  ['Readiness Governor V7', '/api/v47/readiness-governor'],
  ['Execution Lock V6', '/api/v47/execution-lock'],
  ['Next Action', '/api/v47/next-action'],
  ['Audit Ledger', '/api/v47/audit-ledger'],
  ['Mission State V47', '/api/v47/mission-state'],
];

export default function V47Dashboard() {
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
    const mission = data['Mission State V47']?.dummy_mission_state_report_v33 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V46 Baseline', mission.v46_baseline_status || 'UNKNOWN'],
      ['V46 Scores', mission.v46_cumulative_real_scored_count ?? 0],
      ['Controller', mission.stable_sample_threshold_controller_status || 'UNKNOWN'],
      ['V47 Probes', mission.v47_new_real_probe_count ?? 0],
      ['V47 Evidence', mission.v47_new_evidence_count ?? 0],
      ['V47 Settlement', mission.v47_new_settlement_compatible_count ?? 0],
      ['V47 Observed', mission.v47_new_observed_count ?? 0],
      ['V47 Scores', mission.v47_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Score Gap', mission.score_gap_to_100 ?? 0],
      ['Stable Sample', mission.stable_sample_candidate_status || 'UNKNOWN'],
      ['Diversity', mission.sample_diversity_status || 'UNKNOWN'],
      ['Temporal Spread', mission.temporal_spread_status || 'UNKNOWN'],
      ['Drift', mission.calibration_drift_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v28_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v8_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v8_status || 'UNKNOWN'],
      ['Forecast Quality', mission.forecast_quality_ledger_v6_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v7_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v6_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V47 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V47 Readonly Stable Sample Review</h1>
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
