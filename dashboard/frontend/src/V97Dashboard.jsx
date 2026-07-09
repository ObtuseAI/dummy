import StageDashboard from './StageDashboard';

const endpoints = [
  ['Readiness Controller', '/api/v97/readiness-controller'],
  ['V96 Baseline', '/api/v97/v96-baseline'],
  ['Live Submit Readonly Checker', '/api/v97/live-submit-readonly-checker'],
  ['Caps Readonly Checker', '/api/v97/caps-readonly-checker'],
  ['Firewall Adapter Injection Checker', '/api/v97/firewall-adapter-injection-checker'],
  ['No Direct Broker Bypass Proof', '/api/v97/no-direct-broker-bypass-proof'],
  ['No Broker Contact Proof', '/api/v97/no-broker-contact-proof'],
  ['No Private Account Access Proof', '/api/v97/no-private-account-access-proof'],
  ['Secret Redaction Proof', '/api/v97/secret-redaction-proof'],
  ['No Submit No Cancel Proof', '/api/v97/no-submit-no-cancel-proof'],
  ['Readiness Governor', '/api/v97/readiness-governor'],
  ['Execution Lock', '/api/v97/execution-lock'],
  ['Mission State', '/api/v97/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Readiness', 'readiness_controller_status'],
  ['Firewall Adapter', 'firewall_adapter_injection_checker_status'],
  ['Broker Contacted', 'broker_contacted'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V97Dashboard() {
  return <StageDashboard title="Dummy V97 Live Config/Caps/Firewall/Broker Readiness" endpoints={endpoints} missionKey="dummy_mission_state_report_v83" summaryFields={summaryFields} />;
}
