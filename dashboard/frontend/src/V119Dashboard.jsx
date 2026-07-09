import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Gate Controller", "/api/v119/pilot-gate-controller"], ["V118 Baseline", "/api/v119/v118-baseline"], ["Pilot Approval Validator", "/api/v119/pilot-approval-validator"], ["Dry Audit Prerequisite", "/api/v119/dry-audit-prerequisite"], ["Max Pilot Order Count Guard", "/api/v119/max-pilot-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v119/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v119/limit-only-proof"], ["No Market Order Proof", "/api/v119/no-market-order-proof"], ["Pilot Autolock", "/api/v119/pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v119/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v119/readiness-governor"], ["Execution Lock", "/api/v119/execution-lock"], ["Mission State", "/api/v119/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Gate", "pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V119Dashboard() {
  return <StageDashboard title="Dummy V119 Controlled Production Pilot Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v105" summaryFields={summaryFields} />;
}
