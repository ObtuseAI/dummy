import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Local-Only Rehearsal Gate', '/api/v62/local-only-rehearsal-gate'],
  ['V61 Baseline', '/api/v62/v61-baseline'],
  ['Inert Artifact Input Validator', '/api/v62/inert-artifact-input-validator'],
  ['Local-Only Simulation Ledger', '/api/v62/local-only-simulation-ledger'],
  ['No-Broker-Payload Validator', '/api/v62/no-broker-payload-validator'],
  ['No-Order-Intent Validator', '/api/v62/no-order-intent-validator'],
  ['Canary Non-Execution Validator V12', '/api/v62/canary-nonexecution-validator-v12'],
  ['Readiness Governor V22', '/api/v62/readiness-governor'],
  ['Execution Lock V21', '/api/v62/execution-lock'],
  ['Mission State V62', '/api/v62/mission-state'],
];

export default function V62Dashboard() {
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
    const mission = data['Mission State V62']?.dummy_mission_state_report_v48 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V61 Baseline', mission.v61_baseline_status || 'UNKNOWN'],
      ['Rehearsal Gate', mission.local_only_rehearsal_gate_status || 'UNKNOWN'],
      ['Simulation Ledger', mission.local_only_simulation_ledger_status || 'UNKNOWN'],
      ['Sim Entries', mission.simulation_entry_count ?? 0],
      ['No-Broker-Payload', mission.no_broker_payload_validator_status || 'UNKNOWN'],
      ['No-Order-Intent', mission.no_order_intent_validator_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v12_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v22_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v21_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V62 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V62 Local-Only Rehearsal Runner Gate</h1>
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
