import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Controller", "/api/v162/reconcile-controller"], ["V161 Baseline", "/api/v162/v161-baseline"], ["Order State Parser", "/api/v162/order-state-parser"], ["Idempotency Check", "/api/v162/idempotency-check"], ["No Repeat Proof", "/api/v162/no-repeat-proof"], ["No Cancel Default Proof", "/api/v162/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v162/no-private-data-leakage-proof"], ["Pilot Autolock Proof", "/api/v162/pilot-autolock-proof"], ["Readiness Governor", "/api/v162/readiness-governor"], ["Execution Lock", "/api/v162/execution-lock"], ["Mission State", "/api/v162/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile", "reconcile_controller_status"], ["Order State", "order_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V162Dashboard() {
  return <StageDashboard title="Dummy V162 First Real Pilot Reconcile" endpoints={endpoints} missionKey="dummy_mission_state_report_v148" summaryFields={summaryFields} />;
}
