import StageDashboard from './StageDashboard';

const endpoints = [["Livebrokerfirewall Injection Appliance Controller", "/api/v269/livebrokerfirewall-injection-appliance-controller"], ["V268 Baseline", "/api/v269/v268-baseline"], ["Adapter Descriptor Check", "/api/v269/adapter-descriptor-check"], ["Submit Method Contract", "/api/v269/submit-method-contract"], ["Response Shape Check", "/api/v269/response-shape-check"], ["Idempotency Support Check", "/api/v269/idempotency-support-check"], ["Limit Only Enforcement Check", "/api/v269/limit-only-enforcement-check"], ["Market Order Rejection Check", "/api/v269/market-order-rejection-check"], ["Cancel Denial Check", "/api/v269/cancel-denial-check"], ["No Direct Broker Bypass Check", "/api/v269/no-direct-broker-bypass-check"], ["Secret Redaction Check", "/api/v269/secret-redaction-check"], ["Failure Code", "/api/v269/failure-code"], ["No Broker Contact Proof", "/api/v269/no-broker-contact-proof"], ["No Submit Proof", "/api/v269/no-submit-proof"], ["Readiness Governor", "/api/v269/readiness-governor"], ["Execution Lock", "/api/v269/execution-lock"], ["Mission State", "/api/v269/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Injection Appliance", "livebrokerfirewall_injection_appliance_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V269Dashboard() {
  return <StageDashboard title="Dummy V269 LiveBrokerFirewall Injection Appliance Contract And Smoke No Broker" endpoints={endpoints} missionKey="dummy_mission_state_report_v255" summaryFields={summaryFields} />;
}
