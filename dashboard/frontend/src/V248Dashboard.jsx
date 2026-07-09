import StageDashboard from './StageDashboard';

const endpoints = [["Adapter Contract Kit Controller", "/api/v248/adapter-contract-kit-controller"], ["V247 Baseline", "/api/v248/v247-baseline"], ["Contract Kit", "/api/v248/contract-kit"], ["Descriptor Present Check", "/api/v248/descriptor-present-check"], ["Injected Adapter Contract Check", "/api/v248/injected-adapter-contract-check"], ["Non Broker Double Check", "/api/v248/non-broker-double-check"], ["Direct Broker Bypass Scan", "/api/v248/direct-broker-bypass-scan"], ["Market Order Rejection Check", "/api/v248/market-order-rejection-check"], ["Failure Code", "/api/v248/failure-code"], ["No Broker Contact Proof", "/api/v248/no-broker-contact-proof"], ["No Submit Proof", "/api/v248/no-submit-proof"], ["Readiness Governor", "/api/v248/readiness-governor"], ["Execution Lock", "/api/v248/execution-lock"], ["Mission State", "/api/v248/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Adapter Contract Kit", "adapter_contract_kit_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V248Dashboard() {
  return <StageDashboard title="Dummy V248 Livebrokerfirewall Adapter Contract Kit No Broker Contact" endpoints={endpoints} missionKey="dummy_mission_state_report_v234" summaryFields={summaryFields} />;
}
