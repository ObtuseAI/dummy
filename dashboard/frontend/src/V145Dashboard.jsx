import StageDashboard from './StageDashboard';

const endpoints = [["Closeout Controller", "/api/v145/closeout-controller"], ["V144 Baseline", "/api/v145/v144-baseline"], ["Pilot Status Summary", "/api/v145/pilot-status-summary"], ["Repeat Status Summary", "/api/v145/repeat-status-summary"], ["Total Live Order Count", "/api/v145/total-live-order-count"], ["Scale Status Summary", "/api/v145/scale-status-summary"], ["Controlled Operation Status Summary", "/api/v145/controlled-operation-status-summary"], ["Autonomy Blocker Map", "/api/v145/autonomy-blocker-map"], ["Live Proof Gap Map", "/api/v145/live-proof-gap-map"], ["Risk Proof Gap Map", "/api/v145/risk-proof-gap-map"], ["Abstention Proof Gap Map", "/api/v145/abstention-proof-gap-map"], ["Next Action Matrix", "/api/v145/next-action-matrix"], ["No Scale Proof", "/api/v145/no-scale-proof"], ["No Autonomy Proof", "/api/v145/no-autonomy-proof"], ["No New Order Proof", "/api/v145/no-new-order-proof"], ["Readiness Governor", "/api/v145/readiness-governor"], ["Execution Lock", "/api/v145/execution-lock"], ["Mission State", "/api/v145/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Closeout", "closeout_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Total Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V145Dashboard() {
  return <StageDashboard title="Dummy V145 Production Pilot Closeout & Next-Phase Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v131" summaryFields={summaryFields} />;
}
