import StageDashboard from './StageDashboard';

const endpoints = [
  ['Autonomy Review Controller', '/api/v115/autonomy-review-controller'],
  ['V114 Baseline', '/api/v115/v114-baseline'],
  ['Autonomy Review Approval Validator', '/api/v115/autonomy-review-approval-validator'],
  ['Campaign Session Evidence Prerequisite', '/api/v115/campaign-session-evidence-prerequisite'],
  ['Risk Abstention Prerequisite', '/api/v115/risk-abstention-prerequisite'],
  ['Broker Firewall Prerequisite', '/api/v115/broker-firewall-prerequisite'],
  ['Live Submit Caps Control Prerequisite', '/api/v115/live-submit-caps-control-prerequisite'],
  ['Autonomy Eligibility Status', '/api/v115/autonomy-eligibility-status'],
  ['No Autonomous Order Proof', '/api/v115/no-autonomous-order-proof'],
  ['No Auto Scale Proof', '/api/v115/no-auto-scale-proof'],
  ['Readiness Governor', '/api/v115/readiness-governor'],
  ['Execution Lock', '/api/v115/execution-lock'],
  ['Mission State', '/api/v115/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Autonomy Review', 'autonomy_review_controller_status'],
  ['Eligibility', 'autonomy_eligibility_status'],
  ['Autonomous Trading', 'autonomous_trading_enabled'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V115Dashboard() {
  return <StageDashboard title='Dummy V115 Autonomous Candidate Review' endpoints={endpoints} missionKey='dummy_mission_state_report_v101' summaryFields={summaryFields} />;
}
