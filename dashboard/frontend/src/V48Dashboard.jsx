import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Stable Sample Review Controller', '/api/v48/stable-sample-review-controller'],
  ['Exact Gate V16', '/api/v48/exact-gate'],
  ['V47 Baseline', '/api/v48/v47-baseline'],
  ['Robustness Review', '/api/v48/robustness-review'],
  ['Drift Reliability', '/api/v48/drift-reliability'],
  ['Locked Rehearsal Gate Design', '/api/v48/locked-rehearsal-gate-design'],
  ['Readiness Governor V8', '/api/v48/readiness-governor'],
  ['Execution Lock V7', '/api/v48/execution-lock'],
  ['Audit Ledger', '/api/v48/audit-ledger'],
  ['Mission State V48', '/api/v48/mission-state'],
];

export default function V48Dashboard() {
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
    const mission = data['Mission State V48']?.dummy_mission_state_report_v34 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V47 Baseline', mission.v47_baseline_status || 'UNKNOWN'],
      ['V47 Scores', mission.v47_cumulative_real_scored_count ?? 0],
      ['V48 Scores', mission.v48_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Review', mission.stable_sample_review_verdict || 'UNKNOWN'],
      ['Robustness', mission.robustness_review_status || 'UNKNOWN'],
      ['Drift', mission.v48_drift_reliability_review_status || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v29_status || 'UNKNOWN'],
      ['Market Reliability', mission.market_class_reliability_v9_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v9_status || 'UNKNOWN'],
      ['Forecast', mission.forecast_quality_ledger_v7_status || 'UNKNOWN'],
      ['Rehearsal Design', mission.locked_rehearsal_gate_design_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v8_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_v7_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V48 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V48 Readonly Stable Sample Review</h1>
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
