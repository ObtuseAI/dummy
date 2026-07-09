import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Pilot Gate Controller", "/api/v144/repeat-pilot-gate-controller"], ["V143 Baseline", "/api/v144/v143-baseline"], ["Repeat Approval Validator", "/api/v144/repeat-approval-validator"], ["First Pilot Review Prerequisite", "/api/v144/first-pilot-review-prerequisite"], ["Max Repeat Order Count Guard", "/api/v144/max-repeat-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v144/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v144/limit-only-proof"], ["No Market Order Proof", "/api/v144/no-market-order-proof"], ["Repeat Pilot Autolock", "/api/v144/repeat-pilot-autolock"], ["No Campaign Auto Start Proof", "/api/v144/no-campaign-auto-start-proof"], ["Readiness Governor", "/api/v144/readiness-governor"], ["Execution Lock", "/api/v144/execution-lock"], ["Mission State", "/api/v144/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V144Dashboard() {
  return <StageDashboard title="Dummy V144 Repeat Production Pilot Fire On Full Auth" endpoints={endpoints} missionKey="dummy_mission_state_report_v130" summaryFields={summaryFields} />;
}
