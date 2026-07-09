import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Reconcile Controller", "/api/v168/repeat-reconcile-controller"], ["V167 Baseline", "/api/v168/v167-baseline"], ["Order State Parser", "/api/v168/order-state-parser"], ["Idempotency Check", "/api/v168/idempotency-check"], ["No Repeat Proof", "/api/v168/no-repeat-proof"], ["No Cancel Default Proof", "/api/v168/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v168/no-private-data-leakage-proof"], ["Repeat Pilot Autolock Proof", "/api/v168/repeat-pilot-autolock-proof"], ["Readiness Governor", "/api/v168/readiness-governor"], ["Execution Lock", "/api/v168/execution-lock"], ["Mission State", "/api/v168/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Reconcile", "repeat_reconcile_controller_status"], ["Order State", "order_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V168Dashboard() {
  return <StageDashboard title="Dummy V168 Repeat Pilot Reconcile" endpoints={endpoints} missionKey="dummy_mission_state_report_v154" summaryFields={summaryFields} />;
}
