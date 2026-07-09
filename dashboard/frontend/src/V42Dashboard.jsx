import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Calibration Controller', '/api/v42/calibration-controller'],
  ['Exact Gate V10', '/api/v42/exact-gate'],
  ['V41 Baseline', '/api/v42/v41-baseline'],
  ['Sample Extension', '/api/v42/sample-extension'],
  ['Sample Quality', '/api/v42/sample-quality'],
  ['Calibration Metrics', '/api/v42/calibration-metrics'],
  ['Tier Governor', '/api/v42/calibration-tier-governor'],
  ['Source Truth V23', '/api/v42/source-truth-v23'],
  ['Market-Class Reliability', '/api/v42/market-class-reliability'],
  ['No-Trade Discipline', '/api/v42/no-trade-discipline'],
  ['Forecast Quality Ledger', '/api/v42/forecast-quality-ledger'],
  ['Readiness Governor', '/api/v42/readiness-governor'],
  ['Execution Lock', '/api/v42/execution-lock'],
  ['Next Action', '/api/v42/next-action'],
  ['Audit Ledger', '/api/v42/audit-ledger'],
  ['Mission State V42', '/api/v42/mission-state'],
];

export default function V42Dashboard() {
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
    const mission = data['Mission State V42']?.dummy_mission_state_report_v28 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V41 Baseline', mission.v41_baseline_status || 'UNKNOWN'],
      ['V41 Scores', mission.v41_cumulative_real_scored_count ?? 0],
      ['V42 Extension', mission.optional_sample_extension_status || 'UNKNOWN'],
      ['V42 Probes', mission.v42_new_real_probe_count ?? 0],
      ['V42 Evidence', mission.v42_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v42_duplicate_stale_excluded_count ?? 0],
      ['V42 Settlement', mission.v42_new_settlement_compatible_count ?? 0],
      ['V42 Observed', mission.v42_new_observed_count ?? 0],
      ['V42 Scores', mission.v42_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Sample Quality', mission.sample_quality_status || 'UNKNOWN'],
      ['Metrics', mission.calibration_metrics_status || 'UNKNOWN'],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v23_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v3_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v3_status || 'UNKNOWN'],
      ['Forecast Ledger', mission.forecast_quality_ledger_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V42 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V42 Calibration Readiness Governor</h1>
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
