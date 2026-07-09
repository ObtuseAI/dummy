import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Controller", "/api/v200/reconcile-controller"], ["V199 Baseline", "/api/v200/v199-baseline"], ["State Parser", "/api/v200/state-parser"], ["Proof Target Classifier", "/api/v200/proof-target-classifier"], ["Idempotency Check", "/api/v200/idempotency-check"], ["No Repeat Proof", "/api/v200/no-repeat-proof"], ["No Cancel Default Proof", "/api/v200/no-cancel-default-proof"], ["No Private Data Leakage Proof", "/api/v200/no-private-data-leakage-proof"], ["Proof Autolock", "/api/v200/proof-autolock"], ["Readiness Governor", "/api/v200/readiness-governor"], ["Execution Lock", "/api/v200/execution-lock"], ["Mission State", "/api/v200/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile", "reconcile_controller_status"], ["Order State", "order_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V200Dashboard() {
  return <StageDashboard title="Dummy V200 First Live-Proof Reconcile" endpoints={endpoints} missionKey="dummy_mission_state_report_v186" summaryFields={summaryFields} />;
}
