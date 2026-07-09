import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Operation Lock Controller", "/api/v174/controlled-operation-lock-controller"], ["V173 Baseline", "/api/v174/v173-baseline"], ["Repeat Authority Summary", "/api/v174/repeat-authority-summary"], ["Repeat Preflight Summary", "/api/v174/repeat-preflight-summary"], ["Repeat Fire Summary", "/api/v174/repeat-fire-summary"], ["Repeat Reconcile Summary", "/api/v174/repeat-reconcile-summary"], ["Repeat Forensic Summary", "/api/v174/repeat-forensic-summary"], ["Pilot Pair Audit Summary", "/api/v174/pilot-pair-audit-summary"], ["Scale Evidence Summary", "/api/v174/scale-evidence-summary"], ["Controlled Operation Quorum Summary", "/api/v174/controlled-operation-quorum-summary"], ["Dry Session Summary", "/api/v174/dry-session-summary"], ["Total Live Order Count", "/api/v174/total-live-order-count"], ["Next Action Matrix", "/api/v174/next-action-matrix"], ["No Scale Proof", "/api/v174/no-scale-proof"], ["No Autonomy Proof", "/api/v174/no-autonomy-proof"], ["No New Order Proof", "/api/v174/no-new-order-proof"], ["Readiness Governor", "/api/v174/readiness-governor"], ["Execution Lock", "/api/v174/execution-lock"], ["Mission State", "/api/v174/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Operation Lock", "controlled_operation_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Total Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V174Dashboard() {
  return <StageDashboard title="Dummy V174 Controlled Operation Lock V4" endpoints={endpoints} missionKey="dummy_mission_state_report_v160" summaryFields={summaryFields} />;
}
