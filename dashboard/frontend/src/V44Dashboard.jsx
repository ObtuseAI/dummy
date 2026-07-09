import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Readonly Observer Scaleout Controller', '/api/v44/observer-scaleout-controller'],
  ['Exact Gate V12', '/api/v44/exact-gate'],
  ['V43 Baseline', '/api/v44/v43-baseline'],
  ['Observer Lanes', '/api/v44/observer-lanes'],
  ['Source Rotation', '/api/v44/source-rotation'],
  ['Evidence Ledger', '/api/v44/evidence-ledger'],
  ['Settlement Observation', '/api/v44/settlement-observation'],
  ['Score Expansion', '/api/v44/score-expansion'],
  ['Sample Diversity', '/api/v44/sample-diversity'],
  ['Calibration Stability', '/api/v44/calibration-stability'],
  ['Source Truth V25', '/api/v44/source-truth-v25'],
  ['Market-Class Reliability', '/api/v44/market-class-reliability'],
  ['No-Trade Trend', '/api/v44/no-trade-trend'],
  ['Forecast Quality Trend', '/api/v44/forecast-quality-trend'],
  ['Readiness Governor', '/api/v44/readiness-governor'],
  ['Execution Lock', '/api/v44/execution-lock'],
  ['Next Action', '/api/v44/next-action'],
  ['Audit Ledger', '/api/v44/audit-ledger'],
  ['Mission State V44', '/api/v44/mission-state'],
];

export default function V44Dashboard() {
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
    const mission = data['Mission State V44']?.dummy_mission_state_report_v30 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V43 Baseline', mission.v43_baseline_status || 'UNKNOWN'],
      ['V43 Scores', mission.v43_cumulative_real_scored_count ?? 0],
      ['Scaleout', mission.observer_scaleout_status || 'UNKNOWN'],
      ['Lane Isolation', mission.observer_lane_isolation_status || 'UNKNOWN'],
      ['Source Rotation', mission.source_rotation_status || 'UNKNOWN'],
      ['V44 Probes', mission.v44_new_real_probe_count ?? 0],
      ['V44 Evidence', mission.v44_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v44_duplicate_stale_excluded_count ?? 0],
      ['V44 Settlement', mission.v44_new_settlement_compatible_count ?? 0],
      ['V44 Observed', mission.v44_new_observed_count ?? 0],
      ['V44 Scores', mission.v44_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Diversity', mission.sample_diversity_status || 'UNKNOWN'],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Calibration Stability', mission.calibration_stability_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v25_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v5_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v5_status || 'UNKNOWN'],
      ['Forecast Trend', mission.forecast_quality_ledger_v3_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v4_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v3_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V44 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V44 Readonly Observer Scaleout</h1>
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
