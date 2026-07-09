import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Spine V2 Controller", "/api/v220/reconcile-spine-v2-controller"], ["V219 Baseline", "/api/v220/v219-baseline"], ["Proof State Parser", "/api/v220/proof-state-parser"], ["Proof Target Classifier", "/api/v220/proof-target-classifier"], ["Idempotency Verification", "/api/v220/idempotency-verification"], ["Proof Lock Recheck", "/api/v220/proof-lock-recheck"], ["No Repeat Proof", "/api/v220/no-repeat-proof"], ["No Cancel Default Proof", "/api/v220/no-cancel-default-proof"], ["Private Data Redaction", "/api/v220/private-data-redaction"], ["Readiness Governor", "/api/v220/readiness-governor"], ["Execution Lock", "/api/v220/execution-lock"], ["Mission State", "/api/v220/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile Spine", "reconcile_spine_v2_controller_status"], ["Order State", "order_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V220Dashboard() {
  return <StageDashboard title="Dummy V220 Reconcile Spine V2 Proof State And Lock Recheck" endpoints={endpoints} missionKey="dummy_mission_state_report_v206" summaryFields={summaryFields} />;
}
