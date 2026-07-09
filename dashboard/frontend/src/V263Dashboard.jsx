import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Forensic Auto Pipeline V4 Controller", "/api/v263/reconcile-forensic-auto-pipeline-v4-controller"], ["V262 Baseline", "/api/v263/v262-baseline"], ["Load Proof Intake", "/api/v263/load-proof-intake"], ["Classify State", "/api/v263/classify-state"], ["Verify Idempotency", "/api/v263/verify-idempotency"], ["Verify Proof Lock", "/api/v263/verify-proof-lock"], ["Forensic Review", "/api/v263/forensic-review"], ["Update Route Decision", "/api/v263/update-route-decision"], ["Update Completion Score", "/api/v263/update-completion-score"], ["No Cancel Default Proof", "/api/v263/no-cancel-default-proof"], ["No New Order Proof", "/api/v263/no-new-order-proof"], ["Private Data Redaction", "/api/v263/private-data-redaction"], ["Readiness Governor", "/api/v263/readiness-governor"], ["Execution Lock", "/api/v263/execution-lock"], ["Mission State", "/api/v263/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile+Forensic V4", "reconcile_forensic_auto_pipeline_v4_controller_status"], ["Order State", "order_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V263Dashboard() {
  return <StageDashboard title="Dummy V263 Reconcile Forensic Auto Pipeline V4 After Proof Intake" endpoints={endpoints} missionKey="dummy_mission_state_report_v249" summaryFields={summaryFields} />;
}
