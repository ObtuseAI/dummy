import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Manual Approval Pipeline Controller', '/api/v59/manual-approval-pipeline-controller'],
  ['V58 Baseline', '/api/v59/v58-baseline'],
  ['Manual Approval File Validator V2', '/api/v59/manual-approval-file-validator-v2'],
  ['Inert Quarantine Artifact Factory V3', '/api/v59/inert-quarantine-artifact-factory-v3'],
  ['Artifact Integrity Review V2', '/api/v59/artifact-integrity-review-v2'],
  ['Release Denial V2', '/api/v59/release-denial-v2'],
  ['Canary Non-Execution Validator V9', '/api/v59/canary-nonexecution-validator-v9'],
  ['Holdout Continuation', '/api/v59/holdout-continuation'],
  ['Readiness Governor V19', '/api/v59/readiness-governor'],
  ['Execution Lock V18', '/api/v59/execution-lock'],
  ['Mission State V59', '/api/v59/mission-state'],
];

export default function V59Dashboard() {
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
    const mission = data['Mission State V59']?.dummy_mission_state_report_v45 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V58 Baseline', mission.v58_baseline_status || 'UNKNOWN'],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Pipeline Controller', mission.manual_approval_pipeline_controller_status || 'UNKNOWN'],
      ['Approval File Present', String(mission.dedicated_approval_file_present ?? false)],
      ['Factory V3', mission.inert_quarantine_artifact_factory_v3_status || 'UNKNOWN'],
      ['Instances Created', mission.created_quarantine_instance_count ?? 0],
      ['Integrity Review', mission.artifact_integrity_review_v2_status || 'UNKNOWN'],
      ['Release Denial', mission.release_denial_v2_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v9_status || 'UNKNOWN'],
      ['Release Lock', mission.QUARANTINE_RELEASE_LOCKED ? 'LOCKED' : 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v19_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v18_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V59 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V59 Manual Approval Pipeline & Release-Denial Hardening</h1>
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
