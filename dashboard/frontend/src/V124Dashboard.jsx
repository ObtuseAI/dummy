import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Operation Gate Controller", "/api/v124/controlled-operation-gate-controller"], ["V123 Baseline", "/api/v124/v123-baseline"], ["Per Order Approval Requirement", "/api/v124/per-order-approval-requirement"], ["Session Approval Requirement", "/api/v124/session-approval-requirement"], ["Risk Governor Requirement", "/api/v124/risk-governor-requirement"], ["Abstention Governor Requirement", "/api/v124/abstention-governor-requirement"], ["Live Submit Operator Controlled", "/api/v124/live-submit-operator-controlled"], ["Caps Operator Controlled", "/api/v124/caps-operator-controlled"], ["No Auto Submit Proof", "/api/v124/no-auto-submit-proof"], ["No Auto Scale Proof", "/api/v124/no-auto-scale-proof"], ["No Market Order Proof", "/api/v124/no-market-order-proof"], ["Readiness Governor", "/api/v124/readiness-governor"], ["Execution Lock", "/api/v124/execution-lock"], ["Mission State", "/api/v124/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Operation Gate", "controlled_operation_gate_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Per-Order Mode", "per_order_approval_required"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V124Dashboard() {
  return <StageDashboard title="Dummy V124 Controlled Operation Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v110" summaryFields={summaryFields} />;
}
