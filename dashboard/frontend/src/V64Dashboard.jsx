import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Firewall Preflight Controller', '/api/v64/firewall-preflight-controller'],
  ['V63 Baseline', '/api/v64/v63-baseline'],
  ['Firewall-Only Path Validator', '/api/v64/firewall-only-path-validator'],
  ['Limit-Order-Only Rule Validator', '/api/v64/limit-order-only-rule-validator'],
  ['No-Market-Order Validator', '/api/v64/no-market-order-validator'],
  ['No-Submit-Call Validator', '/api/v64/no-submit-call-validator'],
  ['No-Cancel-Call Validator', '/api/v64/no-cancel-call-validator'],
  ['No-Private-Account-Access Validator', '/api/v64/no-private-account-access-validator'],
  ['Caps-Readonly Proof', '/api/v64/caps-readonly-proof'],
  ['Live-Submit-Disabled Proof', '/api/v64/live-submit-disabled-proof'],
  ['Kill-Switch Requirement', '/api/v64/kill-switch-requirement-validator'],
  ['Rollback Requirement', '/api/v64/rollback-requirement-validator'],
  ['Idempotency Requirement', '/api/v64/idempotency-requirement-validator'],
  ['Liquidity/Slippage Requirement', '/api/v64/liquidity-slippage-requirement-validator'],
  ['Canary Non-Execution Validator V14', '/api/v64/canary-nonexecution-validator-v14'],
  ['Readiness Governor V24', '/api/v64/readiness-governor'],
  ['Execution Lock V23', '/api/v64/execution-lock'],
  ['Mission State V64', '/api/v64/mission-state'],
];

export default function V64Dashboard() {
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
    const mission = data['Mission State V64']?.dummy_mission_state_report_v50 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V63 Baseline', mission.v63_baseline_status || 'UNKNOWN'],
      ['Preflight Controller', mission.firewall_preflight_controller_status || 'UNKNOWN'],
      ['Limit-Order-Only', mission.limit_order_only_rule_validator_status || 'UNKNOWN'],
      ['No-Submit-Call', mission.no_submit_call_validator_status || 'UNKNOWN'],
      ['No-Private-Account', mission.no_private_account_access_validator_status || 'UNKNOWN'],
      ['Caps Readonly', mission.caps_readonly_proof_status || 'UNKNOWN'],
      ['Live-Submit Disabled', mission.live_submit_disabled_proof_status || 'UNKNOWN'],
      ['Kill-Switch', mission.kill_switch_requirement_validator_status || 'UNKNOWN'],
      ['Rollback', mission.rollback_requirement_validator_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v14_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v24_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v23_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V64 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V64 LiveBrokerFirewall Preflight (Limit-Only, No Submit)</h1>
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
