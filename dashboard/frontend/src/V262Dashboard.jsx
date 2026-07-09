import StageDashboard from './StageDashboard';

const endpoints = [["External Proof Intake V2 Controller", "/api/v262/external-proof-intake-v2-controller"], ["V261 Baseline", "/api/v262/v261-baseline"], ["Intake State Classification", "/api/v262/intake-state-classification"], ["Proof Id Validation", "/api/v262/proof-id-validation"], ["Order Attempt Id Validation", "/api/v262/order-attempt-id-validation"], ["Idempotency Validation", "/api/v262/idempotency-validation"], ["Attempt Status Validation", "/api/v262/attempt-status-validation"], ["Proof Lock Validation", "/api/v262/proof-lock-validation"], ["Adapter Response Shape Validation", "/api/v262/adapter-response-shape-validation"], ["No Cancel Default Proof", "/api/v262/no-cancel-default-proof"], ["No New Order Proof", "/api/v262/no-new-order-proof"], ["Private Data Redaction", "/api/v262/private-data-redaction"], ["Readiness Governor", "/api/v262/readiness-governor"], ["Execution Lock", "/api/v262/execution-lock"], ["Mission State", "/api/v262/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Proof Intake V2", "external_proof_intake_v2_controller_status"], ["Intake State", "intake_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V262Dashboard() {
  return <StageDashboard title="Dummy V262 External Proof Intake V2 Reconcile Ready No Order" endpoints={endpoints} missionKey="dummy_mission_state_report_v248" summaryFields={summaryFields} />;
}
