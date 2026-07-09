import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Gate Controller", "/api/v129/pilot-gate-controller"], ["V128 Baseline", "/api/v129/v128-baseline"], ["Pilot Approval Validator", "/api/v129/pilot-approval-validator"], ["Auth Packet Prerequisite", "/api/v129/auth-packet-prerequisite"], ["Max Pilot Order Count Guard", "/api/v129/max-pilot-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v129/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v129/limit-only-proof"], ["No Market Order Proof", "/api/v129/no-market-order-proof"], ["Pilot Autolock", "/api/v129/pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v129/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v129/readiness-governor"], ["Execution Lock", "/api/v129/execution-lock"], ["Mission State", "/api/v129/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Gate", "pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V129Dashboard() {
  return <StageDashboard title="Dummy V129 Controlled Production Pilot Fire On Full Auth" endpoints={endpoints} missionKey="dummy_mission_state_report_v115" summaryFields={summaryFields} />;
}
