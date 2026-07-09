import StageDashboard from './StageDashboard';

const endpoints = [["Production Lock Controller", "/api/v184/production-lock-controller"], ["V183 Baseline", "/api/v184/v183-baseline"], ["Controlled Operation Approval Summary", "/api/v184/controlled-operation-approval-summary"], ["Session Preflight Summary", "/api/v184/session-preflight-summary"], ["Session Fire Summary", "/api/v184/session-fire-summary"], ["Session Reconcile Summary", "/api/v184/session-reconcile-summary"], ["Session Forensic Summary", "/api/v184/session-forensic-summary"], ["Session Decision Summary", "/api/v184/session-decision-summary"], ["Scale Review Summary", "/api/v184/scale-review-summary"], ["Autonomy Evidence Summary", "/api/v184/autonomy-evidence-summary"], ["Limited Autonomy Dryrun Summary", "/api/v184/limited-autonomy-dryrun-summary"], ["Total Live Order Count", "/api/v184/total-live-order-count"], ["Next Action Matrix", "/api/v184/next-action-matrix"], ["No Scale Proof", "/api/v184/no-scale-proof"], ["No Autonomy Proof", "/api/v184/no-autonomy-proof"], ["No New Order Proof", "/api/v184/no-new-order-proof"], ["Readiness Governor", "/api/v184/readiness-governor"], ["Execution Lock", "/api/v184/execution-lock"], ["Mission State", "/api/v184/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Production Lock", "production_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Total Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V184Dashboard() {
  return <StageDashboard title="Dummy V184 Production Pilot Lock V5" endpoints={endpoints} missionKey="dummy_mission_state_report_v170" summaryFields={summaryFields} />;
}
