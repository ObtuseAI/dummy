import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Forensic Pipeline V2 Controller", "/api/v243/reconcile-forensic-pipeline-v2-controller"], ["V242 Baseline", "/api/v243/v242-baseline"], ["Load Latest Proof Attempt", "/api/v243/load-latest-proof-attempt"], ["Classify State", "/api/v243/classify-state"], ["Verify Idempotency", "/api/v243/verify-idempotency"], ["Verify Proof Lock", "/api/v243/verify-proof-lock"], ["Forensic Review", "/api/v243/forensic-review"], ["Update Proof State Artifact", "/api/v243/update-proof-state-artifact"], ["Update Route Decision", "/api/v243/update-route-decision"], ["Update Scoreboard", "/api/v243/update-scoreboard"], ["No Cancel Default Proof", "/api/v243/no-cancel-default-proof"], ["No New Order Proof", "/api/v243/no-new-order-proof"], ["Private Data Redaction", "/api/v243/private-data-redaction"], ["Readiness Governor", "/api/v243/readiness-governor"], ["Execution Lock", "/api/v243/execution-lock"], ["Mission State", "/api/v243/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile+Forensic V2", "reconcile_forensic_pipeline_v2_controller_status"], ["Order State", "order_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V243Dashboard() {
  return <StageDashboard title="Dummy V243 Reconcile Forensic Pipeline V2 After Execute Once" endpoints={endpoints} missionKey="dummy_mission_state_report_v229" summaryFields={summaryFields} />;
}
