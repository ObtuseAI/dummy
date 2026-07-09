import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Pilot Gate Controller", "/api/v167/repeat-pilot-gate-controller"], ["V166 Baseline", "/api/v167/v166-baseline"], ["Repeat Approval Validator", "/api/v167/repeat-approval-validator"], ["Preflight Prerequisite", "/api/v167/preflight-prerequisite"], ["First Pilot Proof Prerequisite", "/api/v167/first-pilot-proof-prerequisite"], ["Mode Live Authorized Prerequisite", "/api/v167/mode-live-authorized-prerequisite"], ["Max Repeat Order Count Guard", "/api/v167/max-repeat-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v167/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v167/limit-only-proof"], ["No Market Order Proof", "/api/v167/no-market-order-proof"], ["Repeat Pilot Autolock", "/api/v167/repeat-pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v167/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v167/readiness-governor"], ["Execution Lock", "/api/v167/execution-lock"], ["Mission State", "/api/v167/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V167Dashboard() {
  return <StageDashboard title="Dummy V167 Repeat Pilot Fire Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v153" summaryFields={summaryFields} />;
}
