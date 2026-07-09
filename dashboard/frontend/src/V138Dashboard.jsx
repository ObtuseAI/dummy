import StageDashboard from './StageDashboard';

const endpoints = [["Firewall Adapter Controller", "/api/v138/firewall-adapter-controller"], ["V137 Baseline", "/api/v138/v137-baseline"], ["Adapter Interface Checker", "/api/v138/adapter-interface-checker"], ["Firewall Only Proof", "/api/v138/firewall-only-proof"], ["No Direct Broker Bypass Proof", "/api/v138/no-direct-broker-bypass-proof"], ["No Submit Cancel Default Proof", "/api/v138/no-submit-cancel-default-proof"], ["No Private Account Access Proof", "/api/v138/no-private-account-access-proof"], ["Secret Redaction Proof", "/api/v138/secret-redaction-proof"], ["No Broker Contact Proof", "/api/v138/no-broker-contact-proof"], ["Readiness Governor", "/api/v138/readiness-governor"], ["Execution Lock", "/api/v138/execution-lock"], ["Mission State", "/api/v138/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Firewall Adapter", "firewall_adapter_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V138Dashboard() {
  return <StageDashboard title="Dummy V138 Firewall Adapter Contract" endpoints={endpoints} missionKey="dummy_mission_state_report_v124" summaryFields={summaryFields} />;
}
