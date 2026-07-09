import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Locked Rehearsal Preflight Controller', '/api/v50/locked-rehearsal-preflight-controller'],
  ['Exact Gate V18', '/api/v50/exact-gate'],
  ['V49 Baseline', '/api/v50/v49-baseline'],
  ['Rehearsal Gate Lock Contract', '/api/v50/rehearsal-gate-lock-contract'],
  ['Non-Execution Validator V2', '/api/v50/nonexecution-validator-v2'],
  ['Stable Sample Holdout Continuation', '/api/v50/stable-sample-holdout-continuation'],
  ['Readiness Governor V10', '/api/v50/readiness-governor'],
  ['Execution Lock V9', '/api/v50/execution-lock'],
  ['Audit Ledger', '/api/v50/audit-ledger'],
  ['Mission State V50', '/api/v50/mission-state'],
];

export default function V50Dashboard() {
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
    const mission = data['Mission State V50']?.dummy_mission_state_report_v36 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V49 Baseline', mission.v49_baseline_status || 'UNKNOWN'],
      ['V49 Scores', mission.v49_cumulative_real_scored_count ?? 0],
      ['V50 Scores', mission.v50_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Preflight', mission.locked_rehearsal_preflight_status || 'UNKNOWN'],
      ['Contract', mission.rehearsal_gate_lock_contract_status || 'UNKNOWN'],
      ['Holdout', mission.stable_sample_holdout_continuation_status || 'UNKNOWN'],
      ['Non-Execution', mission.nonexecution_validator_v2_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v10_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v9_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V50 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V50 Locked Rehearsal Preflight</h1>
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
