import StageDashboard from './StageDashboard';

const endpoints = [["Limited Session Gate Controller", "/api/v117/limited-session-gate-controller"], ["V116 Baseline", "/api/v117/v116-baseline"], ["Limited Session Approval Validator", "/api/v117/limited-session-approval-validator"], ["Session Budget Lock", "/api/v117/session-budget-lock"], ["Per Order Approval Requirement", "/api/v117/per-order-approval-requirement"], ["Max Session Order Count", "/api/v117/max-session-order-count"], ["No Market Order Proof", "/api/v117/no-market-order-proof"], ["No Auto Submit Proof", "/api/v117/no-auto-submit-proof"], ["Broker Firewall Prerequisite Proof", "/api/v117/broker-firewall-prerequisite-proof"], ["Live Submit Caps Control Proof", "/api/v117/live-submit-caps-control-proof"], ["Readiness Governor", "/api/v117/readiness-governor"], ["Execution Lock", "/api/v117/execution-lock"], ["Mission State", "/api/v117/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Gate", "limited_session_gate_controller_status"], ["Auto Submit", "autonomous_submit_enabled"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V117Dashboard() {
  return <StageDashboard title="Dummy V117 Limited Autonomous Session Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v103" summaryFields={summaryFields} />;
}
