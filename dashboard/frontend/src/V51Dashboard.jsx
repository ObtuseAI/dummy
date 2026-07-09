import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Approval Surface Controller', '/api/v51/approval-surface-controller'],
  ['Exact Gate V19', '/api/v51/exact-gate'],
  ['V50 Baseline', '/api/v51/v50-baseline'],
  ['Rehearsal Approval Policy', '/api/v51/rehearsal-approval-policy'],
  ['Canary Non-Execution Validator', '/api/v51/canary-nonexecution-validator'],
  ['Holdout Continuation', '/api/v51/holdout-continuation'],
  ['Readiness Governor V11', '/api/v51/readiness-governor'],
  ['Execution Lock V10', '/api/v51/execution-lock'],
  ['Audit Ledger', '/api/v51/audit-ledger'],
  ['Mission State V51', '/api/v51/mission-state'],
];

export default function V51Dashboard() {
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
    const mission = data['Mission State V51']?.dummy_mission_state_report_v37 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V50 Baseline', mission.v50_baseline_status || 'UNKNOWN'],
      ['V50 Scores', mission.v50_cumulative_real_scored_count ?? 0],
      ['V51 Scores', mission.v51_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Approval Surface', mission.approval_surface_status || 'UNKNOWN'],
      ['Policy', mission.rehearsal_approval_policy_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_status || 'UNKNOWN'],
      ['Holdout', mission.holdout_continuation_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v11_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v10_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V51 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V51 Approval Surface</h1>
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
