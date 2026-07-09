import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 3 Gate Controller', '/api/v93/order-3-gate-controller'],
  ['V92 Baseline', '/api/v93/v92-baseline'],
  ['Order 3 Approval Validator', '/api/v93/order-3-approval-validator'],
  ['Continuation Decision Validator', '/api/v93/continuation-decision-validator'],
  ['Max 3 Orders Policy', '/api/v93/max-3-orders-policy'],
  ['No Auto Scale Proof', '/api/v93/no-auto-scale-proof'],
  ['Livebrokerfirewall Only Proof', '/api/v93/livebrokerfirewall-only-proof'],
  ['Single Submit Guard', '/api/v93/single-submit-guard'],
  ['Campaign Closeout Lock', '/api/v93/campaign-closeout-lock'],
  ['Readiness Governor', '/api/v93/readiness-governor'],
  ['Execution Lock', '/api/v93/execution-lock'],
  ['Mission State', '/api/v93/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 3 Gate', 'order_3_gate_controller_status'],
  ['Closeout Lock', 'campaign_closeout_lock_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['No-Auto-Scale', 'no_auto_scale_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V93Dashboard() {
  return <StageDashboard title="Dummy V93 Campaign Order 3 Gate & Closeout" endpoints={endpoints} missionKey="dummy_mission_state_report_v79" summaryFields={summaryFields} />;
}
