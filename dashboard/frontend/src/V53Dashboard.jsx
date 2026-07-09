import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Approval Intake', '/api/v53/approval-intake'],
  ['Exact Gate V21', '/api/v53/exact-gate'],
  ['V52 Baseline', '/api/v53/v52-baseline'],
  ['Manifest Dry Policy', '/api/v53/quarantine-manifest-dry-policy'],
  ['Artifact Allowlist', '/api/v53/rehearsal-artifact-allowlist'],
  ['Canary Non-Execution Validator V3', '/api/v53/canary-nonexecution-validator-v3'],
  ['Holdout Continuation', '/api/v53/holdout-continuation'],
  ['Readiness Governor V13', '/api/v53/readiness-governor'],
  ['Execution Lock V12', '/api/v53/execution-lock'],
  ['Audit Ledger', '/api/v53/audit-ledger'],
  ['Mission State V53', '/api/v53/mission-state'],
];

export default function V53Dashboard() {
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
    const mission = data['Mission State V53']?.dummy_mission_state_report_v39 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V52 Baseline', mission.v52_baseline_status || 'UNKNOWN'],
      ['V52 Scores', mission.v52_cumulative_real_scored_count ?? 0],
      ['V53 Scores', mission.v53_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Approval Intake', mission.approval_intake_status || 'UNKNOWN'],
      ['Manifest Policy', mission.quarantine_manifest_dry_policy_status || 'UNKNOWN'],
      ['Allowlist', mission.artifact_allowlist_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v3_status || 'UNKNOWN'],
      ['Holdout', mission.holdout_continuation_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v13_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v12_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V53 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V53 Approval Intake</h1>
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
