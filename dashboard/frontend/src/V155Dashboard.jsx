import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Operation Lock Controller", "/api/v155/controlled-operation-lock-controller"], ["V154 Baseline", "/api/v155/v154-baseline"], ["Authority Intake Summary", "/api/v155/authority-intake-summary"], ["Dry Live Mode Summary", "/api/v155/dry-live-mode-summary"], ["Rehearsal Summary", "/api/v155/rehearsal-summary"], ["Preflight Summary", "/api/v155/preflight-summary"], ["Fire Gate Summary", "/api/v155/fire-gate-summary"], ["Reconcile Summary", "/api/v155/reconcile-summary"], ["Forensic Summary", "/api/v155/forensic-summary"], ["Repeat Preflight Summary", "/api/v155/repeat-preflight-summary"], ["Total Live Order Count", "/api/v155/total-live-order-count"], ["Controlled Operation Status", "/api/v155/controlled-operation-status"], ["Next Action Matrix", "/api/v155/next-action-matrix"], ["No Scale Proof", "/api/v155/no-scale-proof"], ["No Autonomy Proof", "/api/v155/no-autonomy-proof"], ["No New Order Proof", "/api/v155/no-new-order-proof"], ["Readiness Governor", "/api/v155/readiness-governor"], ["Execution Lock", "/api/v155/execution-lock"], ["Mission State", "/api/v155/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Operation Lock", "controlled_operation_lock_controller_status"], ["Operation Status", "controlled_operation_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V155Dashboard() {
  return <StageDashboard title="Dummy V155 Controlled Operation Lock V3" endpoints={endpoints} missionKey="dummy_mission_state_report_v141" summaryFields={summaryFields} />;
}
