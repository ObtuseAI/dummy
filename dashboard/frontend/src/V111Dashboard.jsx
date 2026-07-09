import StageDashboard from './StageDashboard';

const endpoints = [
  ['Scale Gate Controller', '/api/v111/scale-gate-controller'],
  ['V110 Baseline', '/api/v111/v110-baseline'],
  ['Scale Approval Readback', '/api/v111/scale-approval-readback'],
  ['Risk Prerequisite Validator', '/api/v111/risk-prerequisite-validator'],
  ['Production Readiness Prerequisite Validator', '/api/v111/production-readiness-prerequisite-validator'],
  ['Scale Recommendation', '/api/v111/scale-recommendation'],
  ['No Caps Modification Proof', '/api/v111/no-caps-modification-proof'],
  ['No Order Proof', '/api/v111/no-order-proof'],
  ['Readiness Governor', '/api/v111/readiness-governor'],
  ['Execution Lock', '/api/v111/execution-lock'],
  ['Mission State', '/api/v111/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Scale Gate', 'scale_gate_controller_status'],
  ['Recommendation', 'scale_recommendation'],
  ['Caps Changed', 'caps_changed'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V111Dashboard() {
  return <StageDashboard title='Dummy V111 Scale Step 1 Gate' endpoints={endpoints} missionKey='dummy_mission_state_report_v97' summaryFields={summaryFields} />;
}
