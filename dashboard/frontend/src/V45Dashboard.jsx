import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Readonly Observer Continuation Controller', '/api/v45/observer-continuation-controller'],
  ['Exact Gate V13', '/api/v45/exact-gate'],
  ['V44 Baseline', '/api/v45/v44-baseline'],
  ['Observer Lanes', '/api/v45/observer-lanes'],
  ['Source Portfolio', '/api/v45/source-portfolio'],
  ['Evidence Ledger', '/api/v45/evidence-ledger'],
  ['Settlement Observation', '/api/v45/settlement-observation'],
  ['Score Expansion', '/api/v45/score-expansion'],
  ['Diversity Temporal', '/api/v45/diversity-temporal'],
  ['Calibration Drift', '/api/v45/calibration-drift'],
  ['Source Truth V26', '/api/v45/source-truth-v26'],
  ['Market-Class Reliability', '/api/v45/market-class-reliability'],
  ['No-Trade Trend', '/api/v45/no-trade-trend'],
  ['Forecast Quality Trend', '/api/v45/forecast-quality-trend'],
  ['Stable Sample Prep', '/api/v45/stable-sample-prep'],
  ['Readiness Governor', '/api/v45/readiness-governor'],
  ['Execution Lock', '/api/v45/execution-lock'],
  ['Next Action', '/api/v45/next-action'],
  ['Audit Ledger', '/api/v45/audit-ledger'],
  ['Mission State V45', '/api/v45/mission-state'],
];

export default function V45Dashboard() {
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
    const mission = data['Mission State V45']?.dummy_mission_state_report_v31 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V44 Baseline', mission.v44_baseline_status || 'UNKNOWN'],
      ['V44 Scores', mission.v44_cumulative_real_scored_count ?? 0],
      ['Continuation', mission.observer_continuation_status || 'UNKNOWN'],
      ['Lane Continuation', mission.observer_lane_continuation_status || 'UNKNOWN'],
      ['Source Portfolio', mission.source_portfolio_status || 'UNKNOWN'],
      ['V45 Probes', mission.v45_new_real_probe_count ?? 0],
      ['V45 Evidence', mission.v45_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v45_duplicate_stale_excluded_count ?? 0],
      ['V45 Settlement', mission.v45_new_settlement_compatible_count ?? 0],
      ['V45 Observed', mission.v45_new_observed_count ?? 0],
      ['V45 Scores', mission.v45_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Diversity', mission.sample_diversity_status || 'UNKNOWN'],
      ['Temporal Spread', mission.temporal_spread_status || 'UNKNOWN'],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Calibration Stability', mission.calibration_stability_status || 'UNKNOWN'],
      ['Calibration Drift', mission.calibration_drift_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v26_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v6_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v6_status || 'UNKNOWN'],
      ['Forecast Trend', mission.forecast_quality_ledger_v4_status || 'UNKNOWN'],
      ['Stable Prep', mission.stable_sample_prep_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v5_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v4_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V45 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V45 Readonly Observer Continuation</h1>
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

