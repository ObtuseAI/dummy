import StageDashboard from './StageDashboard';

const endpoints = [["Production Lock Controller", "/api/v204/production-lock-controller"], ["V203 Baseline", "/api/v204/v203-baseline"], ["Authority Binder Summary", "/api/v204/authority-binder-summary"], ["Config Caps Quorum Summary", "/api/v204/config-caps-quorum-summary"], ["Firewall Broker Verification Summary", "/api/v204/firewall-broker-verification-summary"], ["Final Quorum Summary", "/api/v204/final-quorum-summary"], ["Fire Gate Summary", "/api/v204/fire-gate-summary"], ["Reconcile Summary", "/api/v204/reconcile-summary"], ["Forensic Summary", "/api/v204/forensic-summary"], ["Scale Autonomy Evidence Summary", "/api/v204/scale-autonomy-evidence-summary"], ["Controlled Operation Status Summary", "/api/v204/controlled-operation-status-summary"], ["Total Live Order Count", "/api/v204/total-live-order-count"], ["Next Action Matrix", "/api/v204/next-action-matrix"], ["No Scale Proof", "/api/v204/no-scale-proof"], ["No Autonomy Proof", "/api/v204/no-autonomy-proof"], ["No New Order Proof", "/api/v204/no-new-order-proof"], ["Readiness Governor", "/api/v204/readiness-governor"], ["Execution Lock", "/api/v204/execution-lock"], ["Mission State", "/api/v204/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Production Lock", "production_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Total Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V204Dashboard() {
  return <StageDashboard title="Dummy V204 Production Lock V7" endpoints={endpoints} missionKey="dummy_mission_state_report_v190" summaryFields={summaryFields} />;
}
