import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Micro-Order Canary Gate Controller', '/api/v65/micro-order-canary-gate-controller'],
  ['V64 Baseline', '/api/v65/v64-baseline'],
  ['Live-Canary Approval Packet Validator', '/api/v65/live-canary-approval-packet-validator'],
  ['Arming State', '/api/v65/arming-state'],
  ['Pre-Submit Denial Proof', '/api/v65/pre-submit-denial-proof'],
  ['Limit-Order-Only Proof', '/api/v65/limit-order-only-proof'],
  ['No-Market-Order Proof', '/api/v65/no-market-order-proof'],
  ['LiveBrokerFirewall-Only Proof', '/api/v65/livebrokerfirewall-only-proof'],
  ['Kill-Switch Proof', '/api/v65/kill-switch-proof'],
  ['Rollback Proof', '/api/v65/rollback-proof'],
  ['Idempotency Proof', '/api/v65/idempotency-proof'],
  ['Exposure/Caps-Readonly Proof', '/api/v65/exposure-caps-readonly-proof'],
  ['Live-Submit-Disabled Proof', '/api/v65/live-submit-disabled-proof'],
  ['Canary Non-Execution Validator V15', '/api/v65/canary-nonexecution-validator-v15'],
  ['Readiness Governor V25', '/api/v65/readiness-governor'],
  ['Execution Lock V24', '/api/v65/execution-lock'],
  ['Mission State V65', '/api/v65/mission-state'],
];

export default function V65Dashboard() {
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
    const mission = data['Mission State V65']?.dummy_mission_state_report_v51 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V64 Baseline', mission.v64_baseline_status || 'UNKNOWN'],
      ['Gate', mission.micro_order_canary_gate_status || 'UNKNOWN'],
      ['Arming State', mission.arming_state || 'UNKNOWN'],
      ['Order Fired', String(mission.order_fired ?? false)],
      ['Prereq Gates OK', String(mission.prerequisite_gates_ok ?? false)],
      ['Pre-Submit Denial', mission.pre_submit_denial_proof_status || 'UNKNOWN'],
      ['Limit-Order-Only', mission.limit_order_only_proof_status || 'UNKNOWN'],
      ['Kill-Switch', mission.kill_switch_proof_status || 'UNKNOWN'],
      ['Rollback', mission.rollback_proof_status || 'UNKNOWN'],
      ['Live-Submit Disabled', mission.live_submit_disabled_proof_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v15_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v25_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v24_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V65 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V65 Operator-Armed Micro-Order Canary Gate (No Submit)</h1>
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
