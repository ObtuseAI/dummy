import StageDashboard from './StageDashboard';

const endpoints = [["Firewall Adapter Doctor Controller", "/api/v238/firewall-adapter-doctor-controller"], ["V237 Baseline", "/api/v238/v237-baseline"], ["Adapter Descriptor Check", "/api/v238/adapter-descriptor-check"], ["Adapter Injected Check", "/api/v238/adapter-injected-check"], ["Submit Method Check", "/api/v238/submit-method-check"], ["Submit Contract Check", "/api/v238/submit-contract-check"], ["No Direct Broker Bypass Check", "/api/v238/no-direct-broker-bypass-check"], ["Market Order Rejected Check", "/api/v238/market-order-rejected-check"], ["Cancel Denied Check", "/api/v238/cancel-denied-check"], ["Secret Redaction Check", "/api/v238/secret-redaction-check"], ["Failure Code", "/api/v238/failure-code"], ["No Broker Contact Proof", "/api/v238/no-broker-contact-proof"], ["No Submit Proof", "/api/v238/no-submit-proof"], ["Readiness Governor", "/api/v238/readiness-governor"], ["Execution Lock", "/api/v238/execution-lock"], ["Mission State", "/api/v238/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Adapter Doctor", "firewall_adapter_doctor_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V238Dashboard() {
  return <StageDashboard title="Dummy V238 Livebrokerfirewall Adapter Doctor Contract Only No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v224" summaryFields={summaryFields} />;
}
