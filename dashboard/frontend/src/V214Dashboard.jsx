import StageDashboard from './StageDashboard';

const endpoints = [["Completion Accelerator Lock Controller", "/api/v214/completion-accelerator-lock-controller"], ["V213 Baseline", "/api/v214/v213-baseline"], ["Baseline Summary", "/api/v214/baseline-summary"], ["Manifest Summary", "/api/v214/manifest-summary"], ["Cockpit Summary", "/api/v214/cockpit-summary"], ["Authority Resolver Summary", "/api/v214/authority-resolver-summary"], ["Live Proof Runner Summary", "/api/v214/live-proof-runner-summary"], ["Reconcile Runner Summary", "/api/v214/reconcile-runner-summary"], ["Forensic Runner Summary", "/api/v214/forensic-runner-summary"], ["Repeat Session Bridge Summary", "/api/v214/repeat-session-bridge-summary"], ["Completion Scoreboard Summary", "/api/v214/completion-scoreboard-summary"], ["Total Live Order Count", "/api/v214/total-live-order-count"], ["Next Action Matrix", "/api/v214/next-action-matrix"], ["No Scale Proof", "/api/v214/no-scale-proof"], ["No Autonomy Proof", "/api/v214/no-autonomy-proof"], ["No New Order Proof", "/api/v214/no-new-order-proof"], ["Readiness Governor", "/api/v214/readiness-governor"], ["Execution Lock", "/api/v214/execution-lock"], ["Mission State", "/api/v214/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Accelerator Lock", "completion_accelerator_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Total Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V214Dashboard() {
  return <StageDashboard title="Dummy V214 Completion Accelerator Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v200" summaryFields={summaryFields} />;
}
