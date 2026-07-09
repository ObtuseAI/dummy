import StageDashboard from './StageDashboard';

const endpoints = [
  ['Repeat Canary Validator', '/api/v80/repeat-canary-validator'],
  ['V79 Baseline', '/api/v80/v79-baseline'],
  ['Exact Second Canary Phrase Validator', '/api/v80/exact-second-canary-phrase-validator'],
  ['First Canary Reconcile Prerequisite', '/api/v80/first-canary-reconcile-prerequisite'],
  ['First Canary Forensic Prerequisite', '/api/v80/first-canary-forensic-prerequisite'],
  ['Stricter Risk Thresholds', '/api/v80/stricter-risk-thresholds'],
  ['No Loss Lock Validator', '/api/v80/no-loss-lock-validator'],
  ['No Drift Lock Validator', '/api/v80/no-drift-lock-validator'],
  ['No Repeat Without Approval Proof', '/api/v80/no-repeat-without-approval-proof'],
  ['Readiness Governor', '/api/v80/readiness-governor'],
  ['Execution Lock', '/api/v80/execution-lock'],
  ['Mission State', '/api/v80/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Second Phrase', 'exact_second_canary_phrase_validator_status'],
  ['First Reconcile Prereq', 'first_canary_reconcile_prerequisite_status'],
  ['No-Repeat-Without-Approval', 'no_repeat_without_approval_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V80Dashboard() {
  return <StageDashboard title="Dummy V80 Repeat Canary Approval Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v66" summaryFields={summaryFields} />;
}
