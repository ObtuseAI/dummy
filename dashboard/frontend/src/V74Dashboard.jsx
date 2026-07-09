import StageDashboard from './StageDashboard';

const endpoints = [
  ['Blocker Closure Controller', '/api/v74/blocker-closure-controller'],
  ['V73 Baseline', '/api/v74/v73-baseline'],
  ['Blocker Classifier', '/api/v74/blocker-classifier'],
  ['Next Action Matrix', '/api/v74/next-action-matrix'],
  ['No Submit Proof', '/api/v74/no-submit-proof'],
  ['Readiness Governor', '/api/v74/readiness-governor'],
  ['Execution Lock', '/api/v74/execution-lock'],
  ['Mission State', '/api/v74/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Blocker Classifier', 'blocker_classifier_status'],
  ['Next-Action Matrix', 'next_action_matrix_status'],
  ['No-Submit', 'no_submit_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V74Dashboard() {
  return <StageDashboard title="Dummy V74 Live-Canary Blocker Closure Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v60" summaryFields={summaryFields} />;
}
