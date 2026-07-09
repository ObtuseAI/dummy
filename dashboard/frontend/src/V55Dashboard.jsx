import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Approval Input Resolver', '/api/v55/dedicated-approval-input-resolver'],
  ['V54 Baseline', '/api/v55/v54-baseline'],
  ['Approval Input Audit Ledger', '/api/v55/approval-input-audit-ledger'],
  ['Quarantine Artifact Instance Guard', '/api/v55/quarantine-artifact-instance-guard'],
  ['Inert Quarantine Artifact Schema V2', '/api/v55/inert-quarantine-artifact-schema-v2'],
  ['Canary Non-Execution Validator V5', '/api/v55/canary-nonexecution-validator-v5'],
  ['Holdout Continuation', '/api/v55/holdout-continuation'],
  ['Readiness Governor V15', '/api/v55/readiness-governor'],
  ['Execution Lock V14', '/api/v55/execution-lock'],
  ['Mission State V55', '/api/v55/mission-state'],
];

export default function V55Dashboard() {
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
    const mission = data['Mission State V55']?.dummy_mission_state_report_v41 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V54 Baseline', mission.v54_baseline_status || 'UNKNOWN'],
      ['V54 Scores', mission.v54_cumulative_real_scored_count ?? 0],
      ['V55 Scores', mission.v55_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Approval Resolver', mission.approval_resolver_status || 'UNKNOWN'],
      ['Approval Resolution', mission.approval_input_resolution || 'UNKNOWN'],
      ['Instance Guard', mission.artifact_instance_guard_status || 'UNKNOWN'],
      ['Artifacts Created', mission.created_quarantine_artifact_count ?? 0],
      ['Release Lock', mission.quarantine_release_lock_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v5_status || 'UNKNOWN'],
      ['Holdout', mission.holdout_continuation_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v15_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v14_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V55 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V55 Dedicated Approval Input Wiring</h1>
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
