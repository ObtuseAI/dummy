import StageDashboard from './StageDashboard';

const endpoints = [
  ['Campaign Audit Controller', '/api/v106/campaign-audit-controller'],
  ['V105 Baseline', '/api/v106/v105-baseline'],
  ['Order Outcome Summary', '/api/v106/order-outcome-summary'],
  ['Fixture Vs Real Distinction', '/api/v106/fixture-vs-real-distinction'],
  ['Fill Reject Cancel Summary', '/api/v106/fill-reject-cancel-summary'],
  ['Slippage Latency Fee Summary', '/api/v106/slippage-latency-fee-summary'],
  ['Edge Vs Fill Reality Review', '/api/v106/edge-vs-fill-reality-review'],
  ['Abstention Quality Review', '/api/v106/abstention-quality-review'],
  ['Risk Governor Performance Review', '/api/v106/risk-governor-performance-review'],
  ['Killswitch Sessionlock Review', '/api/v106/killswitch-sessionlock-review'],
  ['Campaign Closeout Proof', '/api/v106/campaign-closeout-proof'],
  ['No New Order Proof', '/api/v106/no-new-order-proof'],
  ['Readiness Governor', '/api/v106/readiness-governor'],
  ['Execution Lock', '/api/v106/execution-lock'],
  ['Mission State', '/api/v106/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Campaign Audit', 'campaign_audit_controller_status'],
  ['Closeout', 'campaign_closeout_proof_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V106Dashboard() {
  return <StageDashboard title='Dummy V106 Campaign Final Forensic Audit' endpoints={endpoints} missionKey='dummy_mission_state_report_v92' summaryFields={summaryFields} />;
}
