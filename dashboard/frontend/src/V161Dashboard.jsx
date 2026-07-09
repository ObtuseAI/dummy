import StageDashboard from './StageDashboard';

const endpoints = [["First Real Pilot Gate Controller", "/api/v161/first-real-pilot-gate-controller"], ["V160 Baseline", "/api/v161/v160-baseline"], ["Pilot Approval Validator", "/api/v161/pilot-approval-validator"], ["Quorum Prerequisite", "/api/v161/quorum-prerequisite"], ["Mode Live Authorized Prerequisite", "/api/v161/mode-live-authorized-prerequisite"], ["Max Pilot Order Count Guard", "/api/v161/max-pilot-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v161/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v161/limit-only-proof"], ["No Market Order Proof", "/api/v161/no-market-order-proof"], ["Pilot Autolock", "/api/v161/pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v161/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v161/readiness-governor"], ["Execution Lock", "/api/v161/execution-lock"], ["Mission State", "/api/v161/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["First Real Pilot Gate", "first_real_pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V161Dashboard() {
  return <StageDashboard title="Dummy V161 First Real Pilot Order Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v147" summaryFields={summaryFields} />;
}
