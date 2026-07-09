import StageDashboard from './StageDashboard';

const endpoints = [["Firewall Broker Controller", "/api/v197/firewall-broker-controller"], ["V196 Baseline", "/api/v197/v196-baseline"], ["Firewall Adapter Contract Checker", "/api/v197/firewall-adapter-contract-checker"], ["Submit Method Shape Check", "/api/v197/submit-method-shape-check"], ["Market Order Denial", "/api/v197/market-order-denial"], ["Cancel Denial Default", "/api/v197/cancel-denial-default"], ["Direct Broker Bypass Scan", "/api/v197/direct-broker-bypass-scan"], ["Broker Readonly Approval Validator", "/api/v197/broker-readonly-approval-validator"], ["Readonly Capability Checker", "/api/v197/readonly-capability-checker"], ["Allowed Readonly Call List", "/api/v197/allowed-readonly-call-list"], ["Forbidden Call List", "/api/v197/forbidden-call-list"], ["Secret Redaction", "/api/v197/secret-redaction"], ["Account Private Data Minimization", "/api/v197/account-private-data-minimization"], ["No Submit Cancel Proof", "/api/v197/no-submit-cancel-proof"], ["Readiness Governor", "/api/v197/readiness-governor"], ["Execution Lock", "/api/v197/execution-lock"], ["Mission State", "/api/v197/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Firewall/Broker", "firewall_broker_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V197Dashboard() {
  return <StageDashboard title="Dummy V197 Firewall & Broker Read-Only Verification V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v183" summaryFields={summaryFields} />;
}
