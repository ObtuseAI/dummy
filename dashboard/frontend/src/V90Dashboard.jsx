import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Controller', '/api/v90/reconcile-controller'],
  ['V89 Baseline', '/api/v90/v89-baseline'],
  ['Fill Reject Cancel Expired Partial Parser', '/api/v90/fill-reject-cancel-expired-partial-parser'],
  ['Idempotency Check', '/api/v90/idempotency-check'],
  ['No Repeat Submit Proof', '/api/v90/no-repeat-submit-proof'],
  ['Forensic Capture', '/api/v90/forensic-capture'],
  ['Auto Lock After Outcome', '/api/v90/auto-lock-after-outcome'],
  ['Readiness Governor', '/api/v90/readiness-governor'],
  ['Execution Lock', '/api/v90/execution-lock'],
  ['Mission State', '/api/v90/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Reconcile', 'reconcile_controller_status'],
  ['Forensic Capture', 'forensic_capture_status'],
  ['Auto-Lock', 'auto_lock_after_outcome_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V90Dashboard() {
  return <StageDashboard title="Dummy V90 Order 1 Reconcile & Forensic" endpoints={endpoints} missionKey="dummy_mission_state_report_v76" summaryFields={summaryFields} />;
}
