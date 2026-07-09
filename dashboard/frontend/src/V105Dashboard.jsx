import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 3 Controller', '/api/v105/order-3-controller'],
  ['V104 Baseline', '/api/v105/v104-baseline'],
  ['Order 3 Approval Validator', '/api/v105/order-3-approval-validator'],
  ['Continuation Decision Validator', '/api/v105/continuation-decision-validator'],
  ['Max 3 Orders Policy', '/api/v105/max-3-orders-policy'],
  ['Livebrokerfirewall Only Proof', '/api/v105/livebrokerfirewall-only-proof'],
  ['Limit Only Proof', '/api/v105/limit-only-proof'],
  ['No Market Order Proof', '/api/v105/no-market-order-proof'],
  ['Single Submit Guard', '/api/v105/single-submit-guard'],
  ['Campaign Closeout Lock', '/api/v105/campaign-closeout-lock'],
  ['No Auto Scale Proof', '/api/v105/no-auto-scale-proof'],
  ['Readiness Governor', '/api/v105/readiness-governor'],
  ['Execution Lock', '/api/v105/execution-lock'],
  ['Mission State', '/api/v105/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 3 Gate', 'order_3_controller_status'],
  ['Closeout Lock', 'campaign_closeout_lock_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['No-Auto-Scale', 'no_auto_scale_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V105Dashboard() {
  return <StageDashboard title="Dummy V105 Order 3 Final Gate & Closeout" endpoints={endpoints} missionKey="dummy_mission_state_report_v91" summaryFields={summaryFields} />;
}
