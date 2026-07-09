import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Intake Controller", "/api/v152/reconcile-intake-controller"], ["V151 Baseline", "/api/v152/v151-baseline"], ["Order State Parser", "/api/v152/order-state-parser"], ["Idempotency Check", "/api/v152/idempotency-check"], ["No Repeat Proof", "/api/v152/no-repeat-proof"], ["No Cancel Default Proof", "/api/v152/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v152/no-private-data-leakage-proof"], ["State Autolock", "/api/v152/state-autolock"], ["Readiness Governor", "/api/v152/readiness-governor"], ["Execution Lock", "/api/v152/execution-lock"], ["Mission State", "/api/v152/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile Intake", "reconcile_intake_controller_status"], ["Order State", "order_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V152Dashboard() {
  return <StageDashboard title="Dummy V152 Real Pilot Reconcile Intake" endpoints={endpoints} missionKey="dummy_mission_state_report_v138" summaryFields={summaryFields} />;
}
