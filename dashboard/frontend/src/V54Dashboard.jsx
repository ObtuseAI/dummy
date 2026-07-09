import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Approval Controller', '/api/v54/exact-approval-controller'],
  ['V53 Baseline', '/api/v54/v53-baseline'],
  ['Artifact Factory', '/api/v54/inert-quarantine-artifact-factory'],
  ['Release Lock', '/api/v54/quarantine-release-lock'],
  ['Canary Non-Execution Validator V4', '/api/v54/canary-nonexecution-validator-v4'],
  ['Holdout Continuation', '/api/v54/holdout-continuation'],
  ['Readiness Governor V14', '/api/v54/readiness-governor'],
  ['Execution Lock V13', '/api/v54/execution-lock'],
  ['Audit Ledger', '/api/v54/audit-ledger'],
  ['Mission State V54', '/api/v54/mission-state'],
];

export default function V54Dashboard() {
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
    const mission = data['Mission State V54']?.dummy_mission_state_report_v40 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V53 Baseline', mission.v53_baseline_status || 'UNKNOWN'],
      ['V53 Scores', mission.v53_cumulative_real_scored_count ?? 0],
      ['V54 Scores', mission.v54_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Approval Controller', mission.approval_controller_status || 'UNKNOWN'],
      ['Artifact Factory', mission.artifact_factory_status || 'UNKNOWN'],
      ['Artifacts Created', mission.created_quarantine_artifact_count ?? 0],
      ['Release Lock', mission.quarantine_release_lock_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v4_status || 'UNKNOWN'],
      ['Holdout', mission.holdout_continuation_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v14_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v13_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V54 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V54 Approval Actuated Quarantine</h1>
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
