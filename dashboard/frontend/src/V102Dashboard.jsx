import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 2 Gate Controller', '/api/v102/order-2-gate-controller'],
  ['V101 Baseline', '/api/v102/v101-baseline'],
  ['Order 2 Approval Validator', '/api/v102/order-2-approval-validator'],
  ['Campaign Approval Still Valid', '/api/v102/campaign-approval-still-valid'],
  ['Order 1 Reconcile Prerequisite', '/api/v102/order-1-reconcile-prerequisite'],
  ['Order 1 Forensic Prerequisite', '/api/v102/order-1-forensic-prerequisite'],
  ['Stricter Risk Threshold', '/api/v102/stricter-risk-threshold'],
  ['No Loss Lock', '/api/v102/no-loss-lock'],
  ['No Drift Lock', '/api/v102/no-drift-lock'],
  ['No Repeat Without Approval Proof', '/api/v102/no-repeat-without-approval-proof'],
  ['Readiness Governor', '/api/v102/readiness-governor'],
  ['Execution Lock', '/api/v102/execution-lock'],
  ['Mission State', '/api/v102/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 2 Gate', 'order_2_gate_controller_status'],
  ['Order 2 Approval', 'order_2_approval_validator_status'],
  ['Order 1 Reconcile Prereq', 'order_1_reconcile_prerequisite_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V102Dashboard() {
  return <StageDashboard title="Dummy V102 Order 2 Approval & Repeat Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v88" summaryFields={summaryFields} />;
}
