import StageDashboard from './StageDashboard';

const endpoints = [
  ['Second Canary Gate Controller', '/api/v73/second-canary-gate-controller'],
  ['V72 Baseline', '/api/v73/v72-baseline'],
  ['Repeat-Canary Eligibility', '/api/v73/repeat-canary-eligibility'],
  ['Stricter Approval Requirement', '/api/v73/stricter-approval-requirement'],
  ['Stricter Risk Threshold Requirement', '/api/v73/stricter-risk-threshold-requirement'],
  ['No-Auto-Scale Proof', '/api/v73/no-auto-scale-proof'],
  ['No-Submit Proof', '/api/v73/no-submit-proof'],
  ['Live-Submit/Caps Unchanged Proof', '/api/v73/live-submit-caps-unchanged-proof'],
  ['Readiness Governor V33', '/api/v73/readiness-governor'],
  ['Execution Lock V32', '/api/v73/execution-lock'],
  ['Mission State V73', '/api/v73/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V72 Baseline', 'v72_baseline_status'],
  ['Second Canary Gate', 'second_canary_gate_controller_status'],
  ['Eligibility', 'repeat_canary_eligibility_status'],
  ['No-Auto-Scale', 'no_auto_scale_proof_status'],
  ['No-Submit', 'no_submit_proof_status'],
  ['Second Order Submitted', 'second_order_submitted'],
  ['Readiness', 'readiness_governor_v33_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v32_status'],
  ['Next Action', 'current_next_action']
];

export default function V73Dashboard() {
  return <StageDashboard title="Dummy V73 Second Canary Gate (Review-Locked, No Submit)" endpoints={endpoints} missionKey="dummy_mission_state_report_v59" summaryFields={summaryFields} />;
}
