import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Rehearsal Gate Design Review Controller', '/api/v49/rehearsal-gate-design-review-controller'],
  ['Exact Gate V17', '/api/v49/exact-gate'],
  ['V48 Baseline', '/api/v49/v48-baseline'],
  ['Non-Execution Validator', '/api/v49/nonexecution-validator'],
  ['Stable Sample Holdout Audit', '/api/v49/stable-sample-holdout-audit'],
  ['Locked Rehearsal Gate Spec Review', '/api/v49/locked-rehearsal-gate-spec-review'],
  ['Readiness Governor V9', '/api/v49/readiness-governor'],
  ['Execution Lock V8', '/api/v49/execution-lock'],
  ['Audit Ledger', '/api/v49/audit-ledger'],
  ['Mission State V49', '/api/v49/mission-state'],
];

export default function V49Dashboard() {
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
    const mission = data['Mission State V49']?.dummy_mission_state_report_v35 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V48 Baseline', mission.v48_baseline_status || 'UNKNOWN'],
      ['V48 Scores', mission.v48_cumulative_real_scored_count ?? 0],
      ['V49 Scores', mission.v49_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Holdout', mission.stable_sample_holdout_status || 'UNKNOWN'],
      ['Review', mission.locked_rehearsal_gate_review_status || 'UNKNOWN'],
      ['Non-Execution', mission.nonexecution_validator_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v9_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v8_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V49 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V49 Readonly Rehearsal Gate Review</h1>
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
