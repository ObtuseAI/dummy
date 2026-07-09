import StageDashboard from './StageDashboard';

const endpoints = [["Adapter Smoke Kit Controller", "/api/v258/adapter-smoke-kit-controller"], ["V257 Baseline", "/api/v258/v257-baseline"], ["Smoke Checks", "/api/v258/smoke-checks"], ["Submit Shape Check", "/api/v258/submit-shape-check"], ["Response Shape Check", "/api/v258/response-shape-check"], ["Idempotency Support Check", "/api/v258/idempotency-support-check"], ["Market Order Rejection Check", "/api/v258/market-order-rejection-check"], ["No Direct Broker Bypass Check", "/api/v258/no-direct-broker-bypass-check"], ["Secret Redaction Check", "/api/v258/secret-redaction-check"], ["Failure Code", "/api/v258/failure-code"], ["No Broker Contact Proof", "/api/v258/no-broker-contact-proof"], ["No Submit Proof", "/api/v258/no-submit-proof"], ["Readiness Governor", "/api/v258/readiness-governor"], ["Execution Lock", "/api/v258/execution-lock"], ["Mission State", "/api/v258/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Adapter Smoke Kit", "adapter_smoke_kit_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V258Dashboard() {
  return <StageDashboard title="Dummy V258 Live Adapter Smoke Kit Contract And No Bypass" endpoints={endpoints} missionKey="dummy_mission_state_report_v244" summaryFields={summaryFields} />;
}
