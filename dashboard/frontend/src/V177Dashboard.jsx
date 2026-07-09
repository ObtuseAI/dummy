import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Session Gate Controller", "/api/v177/controlled-session-gate-controller"], ["V176 Baseline", "/api/v177/v176-baseline"], ["Controlled Session Approval Validator", "/api/v177/controlled-session-approval-validator"], ["Preflight Prerequisite", "/api/v177/preflight-prerequisite"], ["Pilot Proof Prerequisite", "/api/v177/pilot-proof-prerequisite"], ["Mode Live Authorized Prerequisite", "/api/v177/mode-live-authorized-prerequisite"], ["Per Order Approval Mode", "/api/v177/per-order-approval-mode"], ["Max Session Order Count Guard", "/api/v177/max-session-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v177/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v177/limit-only-proof"], ["No Market Order Proof", "/api/v177/no-market-order-proof"], ["Session Autolock", "/api/v177/session-autolock"], ["No Repeat Session Proof", "/api/v177/no-repeat-session-proof"], ["Readiness Governor", "/api/v177/readiness-governor"], ["Execution Lock", "/api/v177/execution-lock"], ["Mission State", "/api/v177/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Gate", "controlled_session_gate_controller_status"], ["Session Live Orders", "session_live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V177Dashboard() {
  return <StageDashboard title="Dummy V177 Controlled Operation Session Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v163" summaryFields={summaryFields} />;
}
