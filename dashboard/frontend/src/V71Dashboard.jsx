import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Controller', '/api/v71/reconcile-controller'],
  ['V70 Baseline', '/api/v71/v70-baseline'],
  ['Fill/Cancel/Reject/Expired Parser', '/api/v71/fill-cancel-reject-expired-parser'],
  ['Idempotency Check', '/api/v71/idempotency-check'],
  ['No-Repeat-Submit Proof', '/api/v71/no-repeat-submit-proof'],
  ['Cancel Policy Proof', '/api/v71/cancel-policy-proof'],
  ['Audit Ledger', '/api/v71/audit-ledger'],
  ['Auto-Lock After Outcome', '/api/v71/auto-lock-after-outcome'],
  ['Readiness Governor V31', '/api/v71/readiness-governor'],
  ['Execution Lock V30', '/api/v71/execution-lock'],
  ['Mission State V71', '/api/v71/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V70 Baseline', 'v70_baseline_status'],
  ['Reconcile', 'reconcile_controller_status'],
  ['Live Canary Submitted', 'live_canary_submitted'],
  ['No-Repeat-Submit', 'no_repeat_submit_proof_status'],
  ['Auto-Lock', 'auto_lock_after_outcome_status'],
  ['Further Submit Locked', 'further_submit_locked'],
  ['Readiness', 'readiness_governor_v31_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v30_status'],
  ['Next Action', 'current_next_action']
];

export default function V71Dashboard() {
  return <StageDashboard title="Dummy V71 Live Canary Reconcile & Auto-Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v57" summaryFields={summaryFields} />;
}
