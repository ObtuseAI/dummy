import StageDashboard from './StageDashboard';

const endpoints = [
  ['Readiness Controller', '/api/v87/readiness-controller'],
  ['V86 Baseline', '/api/v87/v86-baseline'],
  ['Live Submit Readonly Checker', '/api/v87/live-submit-readonly-checker'],
  ['Caps Readonly Checker', '/api/v87/caps-readonly-checker'],
  ['Firewall Adapter Presence Checker', '/api/v87/firewall-adapter-presence-checker'],
  ['No Direct Broker Bypass Proof', '/api/v87/no-direct-broker-bypass-proof'],
  ['No Broker Contact Proof', '/api/v87/no-broker-contact-proof'],
  ['No Private Account Access Proof', '/api/v87/no-private-account-access-proof'],
  ['No Submit No Cancel Proof', '/api/v87/no-submit-no-cancel-proof'],
  ['Readiness Governor', '/api/v87/readiness-governor'],
  ['Execution Lock', '/api/v87/execution-lock'],
  ['Mission State', '/api/v87/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Readiness', 'readiness_controller_status'],
  ['Firewall Adapter', 'firewall_adapter_presence_checker_status'],
  ['Broker Contacted', 'broker_contacted'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V87Dashboard() {
  return <StageDashboard title="Dummy V87 Live Config/Caps/Firewall Readiness" endpoints={endpoints} missionKey="dummy_mission_state_report_v73" summaryFields={summaryFields} />;
}
