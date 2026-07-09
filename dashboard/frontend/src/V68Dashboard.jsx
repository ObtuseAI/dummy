import StageDashboard from './StageDashboard';

const endpoints = [
  ['Candidate Selector', '/api/v68/candidate-selector'],
  ['V67 Baseline', '/api/v68/v67-baseline'],
  ['Limit-Only Rule', '/api/v68/limit-only-rule'],
  ['No-Market-Order Proof', '/api/v68/no-market-order-proof'],
  ['Tiny-Size Policy', '/api/v68/tiny-size-policy'],
  ['Liquidity/Slippage Policy', '/api/v68/liquidity-slippage-policy'],
  ['Expiry/Cancel Policy', '/api/v68/expiry-cancel-policy'],
  ['No-Submit Candidate Record', '/api/v68/no-submit-candidate-record'],
  ['Candidate Quarantine', '/api/v68/candidate-quarantine'],
  ['No-Order-Intent-For-Execution Proof', '/api/v68/no-order-intent-for-execution-proof'],
  ['Readiness Governor V28', '/api/v68/readiness-governor'],
  ['Execution Lock V27', '/api/v68/execution-lock'],
  ['Mission State V68', '/api/v68/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V67 Baseline', 'v67_baseline_status'],
  ['Candidate Selector', 'candidate_selector_status'],
  ['Limit-Only', 'limit_only_rule_status'],
  ['No-Market-Order', 'no_market_order_proof_status'],
  ['No-Submit Record', 'no_submit_candidate_record_status'],
  ['No-Order-Intent', 'no_order_intent_for_execution_proof_status'],
  ['Readiness', 'readiness_governor_v28_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v27_status'],
  ['Next Action', 'current_next_action']
];

export default function V68Dashboard() {
  return <StageDashboard title="Dummy V68 Micro-Order Candidate Selector" endpoints={endpoints} missionKey="dummy_mission_state_report_v54" summaryFields={summaryFields} />;
}
