import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Real Quarantine Artifact Reviewer', '/api/v60/real-quarantine-artifact-reviewer'],
  ['V59 Baseline', '/api/v60/v59-baseline'],
  ['Artifact Integrity Review V3', '/api/v60/artifact-integrity-review-v3'],
  ['Release Denial V3', '/api/v60/release-denial-v3'],
  ['Tamper Detector', '/api/v60/tamper-detector'],
  ['Canary Non-Execution Validator V10', '/api/v60/canary-nonexecution-validator-v10'],
  ['Readiness Governor V20', '/api/v60/readiness-governor'],
  ['Execution Lock V19', '/api/v60/execution-lock'],
  ['Mission State V60', '/api/v60/mission-state'],
];

export default function V60Dashboard() {
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
    const mission = data['Mission State V60']?.dummy_mission_state_report_v46 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V59 Baseline', mission.v59_baseline_status || 'UNKNOWN'],
      ['Reviewer', mission.real_quarantine_artifact_reviewer_status || 'UNKNOWN'],
      ['Reviewed Count', mission.reviewed_artifact_count ?? 0],
      ['Integrity Review', mission.artifact_integrity_review_v3_status || 'UNKNOWN'],
      ['Release Denial', mission.release_denial_v3_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v10_status || 'UNKNOWN'],
      ['Release Lock', mission.QUARANTINE_RELEASE_LOCKED ? 'LOCKED' : 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v20_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v19_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V60 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V60 Real Quarantine Review & Release-Denial Reproof</h1>
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
