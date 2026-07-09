import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Operator Handoff Controller', '/api/v56/operator-handoff-controller'],
  ['V55 Baseline', '/api/v56/v55-baseline'],
  ['Approval Packet Template', '/api/v56/approval-packet-template'],
  ['Approval Packet Linter V1', '/api/v56/approval-packet-linter'],
  ['Pre-Artifact Lock Review', '/api/v56/pre-artifact-lock-review'],
  ['Canary Non-Execution Validator V6', '/api/v56/canary-nonexecution-validator-v6'],
  ['Readiness Governor V16', '/api/v56/readiness-governor'],
  ['Execution Lock V15', '/api/v56/execution-lock'],
  ['Mission State V56', '/api/v56/mission-state'],
];

export default function V56Dashboard() {
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
    const mission = data['Mission State V56']?.dummy_mission_state_report_v42 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V55 Baseline', mission.v55_baseline_status || 'UNKNOWN'],
      ['V55 Artifacts', mission.v55_created_quarantine_artifact_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Operator Handoff', mission.operator_handoff_status || 'UNKNOWN'],
      ['Template', mission.approval_packet_template_marker || 'UNKNOWN'],
      ['Linter', mission.approval_packet_linter_status || 'UNKNOWN'],
      ['Pre-Artifact Lock', mission.pre_artifact_lock_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v6_status || 'UNKNOWN'],
      ['Approval File Present', String(mission.dedicated_approval_file_present ?? false)],
      ['Release Lock', mission.QUARANTINE_RELEASE_LOCKED ? 'LOCKED' : 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v16_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v15_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V56 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V56 Operator Handoff & Pre-Artifact Lock</h1>
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
