import StageDashboard from './StageDashboard';

const endpoints = [["First Live Proof Gate Controller", "/api/v199/first-live-proof-gate-controller"], ["V198 Baseline", "/api/v199/v198-baseline"], ["Relevant Approval Validator", "/api/v199/relevant-approval-validator"], ["Quorum Prerequisite", "/api/v199/quorum-prerequisite"], ["Mode Live Authorized Prerequisite", "/api/v199/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v199/proof-target-guard"], ["Max Proof Order Count Guard", "/api/v199/max-proof-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v199/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v199/limit-only-proof"], ["No Market Order Proof", "/api/v199/no-market-order-proof"], ["Proof Autolock", "/api/v199/proof-autolock"], ["No Repeat Beyond Limit Proof", "/api/v199/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v199/readiness-governor"], ["Execution Lock", "/api/v199/execution-lock"], ["Mission State", "/api/v199/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Fire Gate", "first_live_proof_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V199Dashboard() {
  return <StageDashboard title="Dummy V199 First Live-Proof Fire Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v185" summaryFields={summaryFields} />;
}
