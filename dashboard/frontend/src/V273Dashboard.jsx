import StageDashboard from './StageDashboard';

const endpoints = [["Proof Intake Reconcile Handoff V3 Controller", "/api/v273/proof-intake-reconcile-handoff-v3-controller"], ["V272 Baseline", "/api/v273/v272-baseline"], ["Handoff State Classification", "/api/v273/handoff-state-classification"], ["Proof Id Validation", "/api/v273/proof-id-validation"], ["Order Attempt Id Validation", "/api/v273/order-attempt-id-validation"], ["Idempotency Validation", "/api/v273/idempotency-validation"], ["Attempt Status Validation", "/api/v273/attempt-status-validation"], ["Proof Lock Validation", "/api/v273/proof-lock-validation"], ["Adapter Response Shape Validation", "/api/v273/adapter-response-shape-validation"], ["No Cancel Default Proof", "/api/v273/no-cancel-default-proof"], ["No New Order Proof", "/api/v273/no-new-order-proof"], ["Private Data Redaction", "/api/v273/private-data-redaction"], ["Readiness Governor", "/api/v273/readiness-governor"], ["Execution Lock", "/api/v273/execution-lock"], ["Mission State", "/api/v273/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Proof Intake Handoff V3", "proof_intake_reconcile_handoff_v3_controller_status"], ["Handoff State", "handoff_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V273Dashboard() {
  return <StageDashboard title="Dummy V273 Proof Intake Reconcile Handoff V3 No New Order" endpoints={endpoints} missionKey="dummy_mission_state_report_v259" summaryFields={summaryFields} />;
}
