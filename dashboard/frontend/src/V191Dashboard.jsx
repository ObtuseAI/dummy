import StageDashboard from './StageDashboard';

const endpoints = [["Limited Autonomy Gate Controller", "/api/v191/limited-autonomy-gate-controller"], ["V190 Baseline", "/api/v191/v190-baseline"], ["Limited Autonomy Gate Approval Validator", "/api/v191/limited-autonomy-gate-approval-validator"], ["Autonomy Quorum Prerequisite", "/api/v191/autonomy-quorum-prerequisite"], ["Shadow Forensic Prerequisite", "/api/v191/shadow-forensic-prerequisite"], ["Controlled Session Proof Prerequisite", "/api/v191/controlled-session-proof-prerequisite"], ["Per Order Approval Requirement", "/api/v191/per-order-approval-requirement"], ["No Auto Submit Proof", "/api/v191/no-auto-submit-proof"], ["No Market Order Proof", "/api/v191/no-market-order-proof"], ["No Scale Proof", "/api/v191/no-scale-proof"], ["No Firewall Submit Access Proof", "/api/v191/no-firewall-submit-access-proof"], ["No Broker Payload Proof", "/api/v191/no-broker-payload-proof"], ["Readiness Governor", "/api/v191/readiness-governor"], ["Execution Lock", "/api/v191/execution-lock"], ["Mission State", "/api/v191/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Autonomy Gate", "limited_autonomy_gate_controller_status"], ["Gate State", "gate_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V191Dashboard() {
  return <StageDashboard title="Dummy V191 Limited Autonomy Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v177" summaryFields={summaryFields} />;
}
