import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Readonly Observer Threshold Pursuit Controller', '/api/v46/threshold-pursuit-controller'],
  ['Exact Gate V14', '/api/v46/exact-gate'],
  ['V45 Baseline', '/api/v46/v45-baseline'],
  ['Observer Lanes', '/api/v46/observer-lanes'],
  ['Source Portfolio', '/api/v46/source-portfolio'],
  ['Evidence Ledger', '/api/v46/evidence-ledger'],
  ['Settlement Observation', '/api/v46/settlement-observation'],
  ['Score Expansion', '/api/v46/score-expansion'],
  ['Diversity Temporal Concentration', '/api/v46/diversity-temporal-concentration'],
  ['Calibration Drift', '/api/v46/calibration-drift'],
  ['Source Truth V27', '/api/v46/source-truth-v27'],
  ['Market-Class Reliability', '/api/v46/market-class-reliability'],
  ['No-Trade Trend', '/api/v46/no-trade-trend'],
  ['Forecast Quality Trend', '/api/v46/forecast-quality-trend'],
  ['Stable Sample Gap', '/api/v46/stable-sample-gap'],
  ['Readiness Governor', '/api/v46/readiness-governor'],
  ['Execution Lock', '/api/v46/execution-lock'],
  ['Next Action', '/api/v46/next-action'],
  ['Audit Ledger', '/api/v46/audit-ledger'],
  ['Mission State V46', '/api/v46/mission-state'],
];

export default function V46Dashboard() {
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
    const mission = data['Mission State V46']?.dummy_mission_state_report_v32 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V45 Baseline', mission.v45_baseline_status || 'UNKNOWN'],
      ['V45 Scores', mission.v45_cumulative_real_scored_count ?? 0],
      ['Threshold Pursuit', mission.observer_threshold_pursuit_status || 'UNKNOWN'],
      ['Lane Health', mission.observer_lane_health_status || 'UNKNOWN'],
      ['Source Portfolio', mission.source_portfolio_status || 'UNKNOWN'],
      ['V46 Probes', mission.v46_new_real_probe_count ?? 0],
      ['V46 Evidence', mission.v46_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v46_duplicate_stale_excluded_count ?? 0],
      ['V46 Settlement', mission.v46_new_settlement_compatible_count ?? 0],
      ['V46 Observed', mission.v46_new_observed_count ?? 0],
      ['V46 Scores', mission.v46_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Diversity', mission.sample_diversity_status || 'UNKNOWN'],
      ['Temporal Spread', mission.temporal_spread_status || 'UNKNOWN'],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Calibration Stability', mission.calibration_stability_status || 'UNKNOWN'],
      ['Calibration Drift', mission.calibration_drift_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v27_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v7_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v7_status || 'UNKNOWN'],
      ['Forecast Trend', mission.forecast_quality_ledger_v5_status || 'UNKNOWN'],
      ['Stable Gap', mission.stable_sample_gap_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v6_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v5_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V46 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V46 Readonly Observer Threshold Pursuit</h1>
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


