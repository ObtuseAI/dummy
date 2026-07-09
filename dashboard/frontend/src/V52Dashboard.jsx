import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Approval Packet Validator', '/api/v52/approval-packet-validator'],
  ['Exact Gate V20', '/api/v52/exact-gate'],
  ['V51 Baseline', '/api/v52/v51-baseline'],
  ['Quarantine Gate', '/api/v52/rehearsal-artifact-quarantine-gate'],
  ['Approval Phrase Policy', '/api/v52/approval-phrase-policy'],
  ['Canary Non-Execution Validator V2', '/api/v52/canary-nonexecution-validator-v2'],
  ['Holdout Continuation', '/api/v52/holdout-continuation'],
  ['Readiness Governor V12', '/api/v52/readiness-governor'],
  ['Execution Lock V11', '/api/v52/execution-lock'],
  ['Audit Ledger', '/api/v52/audit-ledger'],
  ['Mission State V52', '/api/v52/mission-state'],
];

export default function V52Dashboard() {
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
    const mission = data['Mission State V52']?.dummy_mission_state_report_v38 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V51 Baseline', mission.v51_baseline_status || 'UNKNOWN'],
      ['V51 Scores', mission.v51_cumulative_real_scored_count ?? 0],
      ['V52 Scores', mission.v52_new_real_scored_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Packet Validator', mission.approval_packet_validator_status || 'UNKNOWN'],
      ['Phrase Policy', mission.approval_phrase_policy_status || 'UNKNOWN'],
      ['Quarantine Gate', mission.quarantine_gate_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v2_status || 'UNKNOWN'],
      ['Holdout', mission.holdout_continuation_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v12_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v11_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V52 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V52 Approval Packet Gate</h1>
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
