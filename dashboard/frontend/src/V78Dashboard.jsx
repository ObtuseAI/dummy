import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Controller', '/api/v78/reconcile-controller'],
  ['V77 Baseline', '/api/v78/v77-baseline'],
  ['Fill Reject Cancel Expired Parser', '/api/v78/fill-reject-cancel-expired-parser'],
  ['Partial Fill Handler', '/api/v78/partial-fill-handler'],
  ['Idempotency Check', '/api/v78/idempotency-check'],
  ['No Repeat Submit Proof', '/api/v78/no-repeat-submit-proof'],
  ['Reconcile Ledger', '/api/v78/reconcile-ledger'],
  ['Forensic Capture', '/api/v78/forensic-capture'],
  ['Auto Lock After Outcome', '/api/v78/auto-lock-after-outcome'],
  ['Readiness Governor', '/api/v78/readiness-governor'],
  ['Execution Lock', '/api/v78/execution-lock'],
  ['Mission State', '/api/v78/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Forensic Capture', 'forensic_capture_status'],
  ['No-Repeat-Submit', 'no_repeat_submit_proof_status'],
  ['Auto-Lock', 'auto_lock_after_outcome_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V78Dashboard() {
  return <StageDashboard title="Dummy V78 Live Canary Reconcile & Forensic Capture" endpoints={endpoints} missionKey="dummy_mission_state_report_v64" summaryFields={summaryFields} />;
}
