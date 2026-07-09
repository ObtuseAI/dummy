import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Forensic Pipeline Controller", "/api/v231/reconcile-forensic-pipeline-controller"], ["V230 Baseline", "/api/v231/v230-baseline"], ["Proof State Parser", "/api/v231/proof-state-parser"], ["Proof Target Classifier", "/api/v231/proof-target-classifier"], ["Idempotency Verification", "/api/v231/idempotency-verification"], ["Proof Lock Recheck", "/api/v231/proof-lock-recheck"], ["Forensic Fill Reject Summary", "/api/v231/forensic-fill-reject-summary"], ["Forensic Slippage Latency Fee", "/api/v231/forensic-slippage-latency-fee"], ["Forensic Risk Abstention", "/api/v231/forensic-risk-abstention"], ["No Cancel Default Proof", "/api/v231/no-cancel-default-proof"], ["No New Order Proof", "/api/v231/no-new-order-proof"], ["Private Data Redaction", "/api/v231/private-data-redaction"], ["Readiness Governor", "/api/v231/readiness-governor"], ["Execution Lock", "/api/v231/execution-lock"], ["Mission State", "/api/v231/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Reconcile+Forensic", "reconcile_forensic_pipeline_controller_status"], ["Order State", "order_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V231Dashboard() {
  return <StageDashboard title="Dummy V231 Reconcile Forensic Auto Pipeline No New Orders" endpoints={endpoints} missionKey="dummy_mission_state_report_v217" summaryFields={summaryFields} />;
}
