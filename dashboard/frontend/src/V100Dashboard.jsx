import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Controller', '/api/v100/reconcile-controller'],
  ['V99 Baseline', '/api/v100/v99-baseline'],
  ['Fill Reject Cancel Expired Partial Parser', '/api/v100/fill-reject-cancel-expired-partial-parser'],
  ['Idempotency Check', '/api/v100/idempotency-check'],
  ['No Repeat Submit Proof', '/api/v100/no-repeat-submit-proof'],
  ['Forensic Capture', '/api/v100/forensic-capture'],
  ['Auto Lock After Outcome', '/api/v100/auto-lock-after-outcome'],
  ['Readiness Governor', '/api/v100/readiness-governor'],
  ['Execution Lock', '/api/v100/execution-lock'],
  ['Mission State', '/api/v100/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Reconcile', 'reconcile_controller_status'],
  ['Forensic Capture', 'forensic_capture_status'],
  ['Auto-Lock', 'auto_lock_after_outcome_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V100Dashboard() {
  return <StageDashboard title="Dummy V100 Order 1 Reconcile & Forensic" endpoints={endpoints} missionKey="dummy_mission_state_report_v86" summaryFields={summaryFields} />;
}
