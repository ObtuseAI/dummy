import StageDashboard from './StageDashboard';

const endpoints = [
  ['Authorization Packet Controller', '/api/v76/authorization-packet-controller'],
  ['V75 Baseline', '/api/v76/v75-baseline'],
  ['Candidate Tieout', '/api/v76/candidate-tieout'],
  ['Firewall Tieout', '/api/v76/firewall-tieout'],
  ['Caps Live Submit Approval Tieout', '/api/v76/caps-live-submit-approval-tieout'],
  ['Limit Order Only Proof', '/api/v76/limit-order-only-proof'],
  ['No Market Order Proof', '/api/v76/no-market-order-proof'],
  ['Liquidity Slippage Proof', '/api/v76/liquidity-slippage-proof'],
  ['Kill Switch Proof', '/api/v76/kill-switch-proof'],
  ['Rollback Proof', '/api/v76/rollback-proof'],
  ['Idempotency Proof', '/api/v76/idempotency-proof'],
  ['One Order Only Proof', '/api/v76/one-order-only-proof'],
  ['Readiness Governor', '/api/v76/readiness-governor'],
  ['Execution Lock', '/api/v76/execution-lock'],
  ['Mission State', '/api/v76/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['One-Order-Only', 'one_order_only_proof_status'],
  ['No-Market-Order', 'no_market_order_proof_status'],
  ['Caps/Live-Submit Tieout', 'caps_live_submit_approval_tieout_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V76Dashboard() {
  return <StageDashboard title="Dummy V76 Final Single-Canary Authorization Packet" endpoints={endpoints} missionKey="dummy_mission_state_report_v62" summaryFields={summaryFields} />;
}
