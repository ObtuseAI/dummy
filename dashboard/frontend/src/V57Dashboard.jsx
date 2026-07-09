import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Manual Approval File Consumer', '/api/v57/manual-approval-file-consumer'],
  ['V56 Baseline', '/api/v57/v56-baseline'],
  ['Inert Quarantine Instance Factory V2', '/api/v57/inert-quarantine-instance-factory-v2'],
  ['Quarantine Release Lock V2', '/api/v57/quarantine-release-lock-v2'],
  ['Canary Non-Execution Validator V7', '/api/v57/canary-nonexecution-validator-v7'],
  ['Readiness Governor V17', '/api/v57/readiness-governor'],
  ['Execution Lock V16', '/api/v57/execution-lock'],
  ['Mission State V57', '/api/v57/mission-state'],
];

export default function V57Dashboard() {
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
    const mission = data['Mission State V57']?.dummy_mission_state_report_v43 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V56 Baseline', mission.v56_baseline_status || 'UNKNOWN'],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Approval Consumer', mission.manual_approval_file_consumer_status || 'UNKNOWN'],
      ['Approval File Present', String(mission.dedicated_approval_file_present ?? false)],
      ['Instance Factory V2', mission.inert_quarantine_instance_factory_v2_status || 'UNKNOWN'],
      ['Instances Created', mission.created_quarantine_instance_count ?? 0],
      ['Release Lock V2', mission.quarantine_release_lock_v2_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v7_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v17_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v16_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V57 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V57 Manual Approval Consumption & Inert Instances</h1>
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
