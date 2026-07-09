import StageDashboard from './StageDashboard';

const endpoints = [["Firewall Adapter Controller", "/api/v158/firewall-adapter-controller"], ["V157 Baseline", "/api/v158/v157-baseline"], ["Adapter Presence Checker", "/api/v158/adapter-presence-checker"], ["Required Method Contract", "/api/v158/required-method-contract"], ["Submit Method Shape Check", "/api/v158/submit-method-shape-check"], ["Cancel Denial Check", "/api/v158/cancel-denial-check"], ["Market Order Denial Check", "/api/v158/market-order-denial-check"], ["Direct Broker Bypass Scan", "/api/v158/direct-broker-bypass-scan"], ["Secret Redaction", "/api/v158/secret-redaction"], ["No Real Broker Contact Proof", "/api/v158/no-real-broker-contact-proof"], ["No Submit Proof", "/api/v158/no-submit-proof"], ["Readiness Governor", "/api/v158/readiness-governor"], ["Execution Lock", "/api/v158/execution-lock"], ["Mission State", "/api/v158/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Firewall Adapter", "firewall_adapter_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V158Dashboard() {
  return <StageDashboard title="Dummy V158 Firewall Adapter Injection Verification" endpoints={endpoints} missionKey="dummy_mission_state_report_v144" summaryFields={summaryFields} />;
}
