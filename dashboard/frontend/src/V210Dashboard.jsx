import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Runner Controller", "/api/v210/reconcile-runner-controller"], ["V209 Baseline", "/api/v210/v209-baseline"], ["State Parser", "/api/v210/state-parser"], ["Proof Target Classifier", "/api/v210/proof-target-classifier"], ["Idempotency Verification", "/api/v210/idempotency-verification"], ["No Repeat Proof", "/api/v210/no-repeat-proof"], ["No Cancel Default Proof", "/api/v210/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v210/no-private-data-leakage-proof"], ["Proof Autolock", "/api/v210/proof-autolock"], ["Readiness Governor", "/api/v210/readiness-governor"], ["Execution Lock", "/api/v210/execution-lock"], ["Mission State", "/api/v210/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile Runner", "reconcile_runner_controller_status"], ["Order State", "order_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V210Dashboard() {
  return <StageDashboard title="Dummy V210 Reconcile Runner Spine" endpoints={endpoints} missionKey="dummy_mission_state_report_v196" summaryFields={summaryFields} />;
}
