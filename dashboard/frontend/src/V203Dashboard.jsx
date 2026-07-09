import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Operation Status Controller", "/api/v203/controlled-operation-status-controller"], ["V202 Baseline", "/api/v203/v202-baseline"], ["First Live Proof Status Readback", "/api/v203/first-live-proof-status-readback"], ["Reconcile Status Readback", "/api/v203/reconcile-status-readback"], ["Forensic Status Readback", "/api/v203/forensic-status-readback"], ["Scale Autonomy Evidence Readback", "/api/v203/scale-autonomy-evidence-readback"], ["Risk Locks", "/api/v203/risk-locks"], ["Abstention Locks", "/api/v203/abstention-locks"], ["Per Order Approval Requirement", "/api/v203/per-order-approval-requirement"], ["Live Submit Operator Control Proof", "/api/v203/live-submit-operator-control-proof"], ["Caps Operator Control Proof", "/api/v203/caps-operator-control-proof"], ["No Auto Submit Proof", "/api/v203/no-auto-submit-proof"], ["No Market Order Proof", "/api/v203/no-market-order-proof"], ["No Scale Proof", "/api/v203/no-scale-proof"], ["No Autonomy Proof", "/api/v203/no-autonomy-proof"], ["Readiness Governor", "/api/v203/readiness-governor"], ["Execution Lock", "/api/v203/execution-lock"], ["Mission State", "/api/v203/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Operation Status Gate", "controlled_operation_status_controller_status"], ["Operation Status", "controlled_operation_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V203Dashboard() {
  return <StageDashboard title="Dummy V203 Controlled Operation Status Gate V7" endpoints={endpoints} missionKey="dummy_mission_state_report_v189" summaryFields={summaryFields} />;
}
