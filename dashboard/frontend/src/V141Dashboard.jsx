import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Gate Controller", "/api/v141/pilot-gate-controller"], ["V140 Baseline", "/api/v141/v140-baseline"], ["Pilot Approval Validator", "/api/v141/pilot-approval-validator"], ["Final Auth Packet Prerequisite", "/api/v141/final-auth-packet-prerequisite"], ["Max Pilot Order Count Guard", "/api/v141/max-pilot-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v141/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v141/limit-only-proof"], ["No Market Order Proof", "/api/v141/no-market-order-proof"], ["Pilot Autolock", "/api/v141/pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v141/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v141/readiness-governor"], ["Execution Lock", "/api/v141/execution-lock"], ["Mission State", "/api/v141/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Gate", "pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V141Dashboard() {
  return <StageDashboard title="Dummy V141 Controlled Production Pilot Fire On Full Auth" endpoints={endpoints} missionKey="dummy_mission_state_report_v127" summaryFields={summaryFields} />;
}
