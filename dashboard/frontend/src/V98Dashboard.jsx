import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 1 Authorization Controller', '/api/v98/order-1-authorization-controller'],
  ['V97 Baseline', '/api/v98/v97-baseline'],
  ['Candidate Queue Readback', '/api/v98/candidate-queue-readback'],
  ['Approval Readback', '/api/v98/approval-readback'],
  ['Config Firewall Readback', '/api/v98/config-firewall-readback'],
  ['Limit Only Proof', '/api/v98/limit-only-proof'],
  ['No Market Order Proof', '/api/v98/no-market-order-proof'],
  ['Tiny Exposure Proof', '/api/v98/tiny-exposure-proof'],
  ['Liquidity Slippage Proof', '/api/v98/liquidity-slippage-proof'],
  ['Kill Switch Proof', '/api/v98/kill-switch-proof'],
  ['Rollback Proof', '/api/v98/rollback-proof'],
  ['Idempotency Proof', '/api/v98/idempotency-proof'],
  ['No Submit Proof', '/api/v98/no-submit-proof'],
  ['Readiness Governor', '/api/v98/readiness-governor'],
  ['Execution Lock', '/api/v98/execution-lock'],
  ['Mission State', '/api/v98/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Authorization', 'order_1_authorization_controller_status'],
  ['No-Submit', 'no_submit_proof_status'],
  ['Kill-Switch', 'kill_switch_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V98Dashboard() {
  return <StageDashboard title="Dummy V98 Order 1 Final Authorization Tieout" endpoints={endpoints} missionKey="dummy_mission_state_report_v84" summaryFields={summaryFields} />;
}
