import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Quarantine Artifact Reviewer', '/api/v58/quarantine-artifact-reviewer'],
  ['V57 Baseline', '/api/v58/v57-baseline'],
  ['Artifact Integrity Validator', '/api/v58/artifact-integrity-validator'],
  ['Release Denial Proof', '/api/v58/release-denial-proof'],
  ['Canary Non-Execution Validator V8', '/api/v58/canary-nonexecution-validator-v8'],
  ['Readiness Governor V18', '/api/v58/readiness-governor'],
  ['Execution Lock V17', '/api/v58/execution-lock'],
  ['Mission State V58', '/api/v58/mission-state'],
];

export default function V58Dashboard() {
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
    const mission = data['Mission State V58']?.dummy_mission_state_report_v44 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V57 Baseline', mission.v57_baseline_status || 'UNKNOWN'],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Reviewer', mission.quarantine_artifact_reviewer_status || 'UNKNOWN'],
      ['Reviewed Count', mission.reviewed_artifact_count ?? 0],
      ['Integrity Validator', mission.artifact_integrity_validator_status || 'UNKNOWN'],
      ['Release Denial', mission.release_denial_proof_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v8_status || 'UNKNOWN'],
      ['Release Lock', mission.QUARANTINE_RELEASE_LOCKED ? 'LOCKED' : 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v18_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v17_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V58 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V58 Quarantine Reviewer & Release-Denial Proof</h1>
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
