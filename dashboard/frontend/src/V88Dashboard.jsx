import StageDashboard from './StageDashboard';

const endpoints = [
  ['Candidate Queue Controller', '/api/v88/candidate-queue-controller'],
  ['V87 Baseline', '/api/v88/v87-baseline'],
  ['Candidate Scoring Readback', '/api/v88/candidate-scoring-readback'],
  ['Limit Only Candidate Queue', '/api/v88/limit-only-candidate-queue'],
  ['No Market Order Proof', '/api/v88/no-market-order-proof'],
  ['Abstention Governor', '/api/v88/abstention-governor'],
  ['No Submit Candidate Records', '/api/v88/no-submit-candidate-records'],
  ['No Order Intent For Execution Proof', '/api/v88/no-order-intent-for-execution-proof'],
  ['Readiness Governor', '/api/v88/readiness-governor'],
  ['Execution Lock', '/api/v88/execution-lock'],
  ['Mission State', '/api/v88/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Candidate Queue', 'candidate_queue_controller_status'],
  ['Abstention Governor', 'abstention_governor_status'],
  ['Submit Enabled Default', 'submit_enabled_default'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V88Dashboard() {
  return <StageDashboard title="Dummy V88 Candidate Queue & Abstention Governor" endpoints={endpoints} missionKey="dummy_mission_state_report_v74" summaryFields={summaryFields} />;
}
