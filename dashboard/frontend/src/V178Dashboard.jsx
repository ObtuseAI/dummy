import StageDashboard from './StageDashboard';

const endpoints = [["Session Reconcile Controller", "/api/v178/session-reconcile-controller"], ["V177 Baseline", "/api/v178/v177-baseline"], ["Per Order State Parser", "/api/v178/per-order-state-parser"], ["Session Aggregate State", "/api/v178/session-aggregate-state"], ["Idempotency Check", "/api/v178/idempotency-check"], ["No Repeat Session Proof", "/api/v178/no-repeat-session-proof"], ["No Cancel Default Proof", "/api/v178/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v178/no-private-data-leakage-proof"], ["Session Autolock Proof", "/api/v178/session-autolock-proof"], ["Readiness Governor", "/api/v178/readiness-governor"], ["Execution Lock", "/api/v178/execution-lock"], ["Mission State", "/api/v178/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Reconcile", "session_reconcile_controller_status"], ["Session State", "session_state"], ["Session Live Orders", "session_live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V178Dashboard() {
  return <StageDashboard title="Dummy V178 Controlled Session Reconcile" endpoints={endpoints} missionKey="dummy_mission_state_report_v164" summaryFields={summaryFields} />;
}
