import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 2 Gate Controller', '/api/v91/order-2-gate-controller'],
  ['V90 Baseline', '/api/v91/v90-baseline'],
  ['Order 2 Approval Validator', '/api/v91/order-2-approval-validator'],
  ['Order 1 Proof Prerequisite', '/api/v91/order-1-proof-prerequisite'],
  ['Stricter Risk Threshold Validator', '/api/v91/stricter-risk-threshold-validator'],
  ['Single Submit Guard', '/api/v91/single-submit-guard'],
  ['Livebrokerfirewall Submit Adapter', '/api/v91/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v91/post-submit-auto-lock'],
  ['Readiness Governor', '/api/v91/readiness-governor'],
  ['Execution Lock', '/api/v91/execution-lock'],
  ['Mission State', '/api/v91/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 2 Gate', 'order_2_gate_controller_status'],
  ['Order 1 Proof', 'order_1_proof_prerequisite_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V91Dashboard() {
  return <StageDashboard title="Dummy V91 Campaign Order 2 Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v77" summaryFields={summaryFields} />;
}
