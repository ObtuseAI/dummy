import StageDashboard from './StageDashboard';

const endpoints = [
  ['Blocker Closure Controller', '/api/v95/blocker-closure-controller'],
  ['V94 Baseline', '/api/v95/v94-baseline'],
  ['Blocker Map', '/api/v95/blocker-map'],
  ['Next Action Map', '/api/v95/next-action-map'],
  ['No Submit Proof', '/api/v95/no-submit-proof'],
  ['No Broker Contact Proof', '/api/v95/no-broker-contact-proof'],
  ['Readiness Governor', '/api/v95/readiness-governor'],
  ['Execution Lock', '/api/v95/execution-lock'],
  ['Mission State', '/api/v95/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Blocker Closure', 'blocker_closure_controller_status'],
  ['No-Submit', 'no_submit_proof_status'],
  ['No-Broker-Contact', 'no_broker_contact_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V95Dashboard() {
  return <StageDashboard title="Dummy V95 Campaign Blocker Closure Audit V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v81" summaryFields={summaryFields} />;
}
