import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Local Rehearsal Design Controller', '/api/v61/local-rehearsal-design-controller'],
  ['V60 Baseline', '/api/v61/v60-baseline'],
  ['Rehearsal Design Spec', '/api/v61/rehearsal-design-spec'],
  ['Local-Only Execution Denial Proof', '/api/v61/local-only-execution-denial-proof'],
  ['No-Broker/No-Order Proof', '/api/v61/no-broker-no-order-proof'],
  ['Future Approval Phrase Policy', '/api/v61/future-approval-phrase-policy'],
  ['Canary Non-Execution Validator V11', '/api/v61/canary-nonexecution-validator-v11'],
  ['Readiness Governor V21', '/api/v61/readiness-governor'],
  ['Execution Lock V20', '/api/v61/execution-lock'],
  ['Mission State V61', '/api/v61/mission-state'],
];

export default function V61Dashboard() {
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
    const mission = data['Mission State V61']?.dummy_mission_state_report_v47 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V60 Baseline', mission.v60_baseline_status || 'UNKNOWN'],
      ['Design Controller', mission.local_rehearsal_design_controller_status || 'UNKNOWN'],
      ['Execution Denial', mission.local_only_execution_denial_proof_status || 'UNKNOWN'],
      ['No-Broker/No-Order', mission.no_broker_no_order_proof_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v11_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v21_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v20_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V61 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V61 Local Rehearsal Design Gate (Non-Executable)</h1>
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
