import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Operation Gate Controller", "/api/v134/controlled-operation-gate-controller"], ["V133 Baseline", "/api/v134/v133-baseline"], ["Controlled Operation Review Validator", "/api/v134/controlled-operation-review-validator"], ["Per Order Approval Requirement", "/api/v134/per-order-approval-requirement"], ["Session Approval Requirement", "/api/v134/session-approval-requirement"], ["Risk Governor Requirement", "/api/v134/risk-governor-requirement"], ["Abstention Governor Requirement", "/api/v134/abstention-governor-requirement"], ["Live Submit Operator Controlled", "/api/v134/live-submit-operator-controlled"], ["Caps Operator Controlled", "/api/v134/caps-operator-controlled"], ["No Auto Submit Proof", "/api/v134/no-auto-submit-proof"], ["No Auto Scale Proof", "/api/v134/no-auto-scale-proof"], ["No Market Order Proof", "/api/v134/no-market-order-proof"], ["Readiness Governor", "/api/v134/readiness-governor"], ["Execution Lock", "/api/v134/execution-lock"], ["Mission State", "/api/v134/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Operation Gate", "controlled_operation_gate_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Per-Order Mode", "per_order_approval_required"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V134Dashboard() {
  return <StageDashboard title="Dummy V134 Controlled Operation Gate V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v120" summaryFields={summaryFields} />;
}
