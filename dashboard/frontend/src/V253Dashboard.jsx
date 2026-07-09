import StageDashboard from './StageDashboard';

const endpoints = [["Post Execution Intake Bridge Controller", "/api/v253/post-execution-intake-bridge-controller"], ["V252 Baseline", "/api/v253/v252-baseline"], ["Bridge State Classification", "/api/v253/bridge-state-classification"], ["Proof Id Validation", "/api/v253/proof-id-validation"], ["Order Attempt Id Validation", "/api/v253/order-attempt-id-validation"], ["Idempotency Validation", "/api/v253/idempotency-validation"], ["Proof Lock Validation", "/api/v253/proof-lock-validation"], ["Target State Validation", "/api/v253/target-state-validation"], ["No Cancel Default Proof", "/api/v253/no-cancel-default-proof"], ["No New Order Proof", "/api/v253/no-new-order-proof"], ["Private Data Redaction", "/api/v253/private-data-redaction"], ["Readiness Governor", "/api/v253/readiness-governor"], ["Execution Lock", "/api/v253/execution-lock"], ["Mission State", "/api/v253/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Intake Bridge", "post_execution_intake_bridge_controller_status"], ["Bridge State", "bridge_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V253Dashboard() {
  return <StageDashboard title="Dummy V253 Post Execution Intake Bridge Reconcile Forensic Ready" endpoints={endpoints} missionKey="dummy_mission_state_report_v239" summaryFields={summaryFields} />;
}
