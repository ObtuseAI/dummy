import StageDashboard from './StageDashboard';

const endpoints = [["Real Pilot Gate Controller", "/api/v151/real-pilot-gate-controller"], ["V150 Baseline", "/api/v151/v150-baseline"], ["Pilot Approval Validator", "/api/v151/pilot-approval-validator"], ["Preflight Prerequisite", "/api/v151/preflight-prerequisite"], ["Mode Live Authorized Prerequisite", "/api/v151/mode-live-authorized-prerequisite"], ["Max Pilot Order Count Guard", "/api/v151/max-pilot-order-count-guard"], ["Livebrokerfirewall Only Proof", "/api/v151/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v151/limit-only-proof"], ["No Market Order Proof", "/api/v151/no-market-order-proof"], ["Pilot Autolock", "/api/v151/pilot-autolock"], ["No Repeat Beyond Limit Proof", "/api/v151/no-repeat-beyond-limit-proof"], ["Readiness Governor", "/api/v151/readiness-governor"], ["Execution Lock", "/api/v151/execution-lock"], ["Mission State", "/api/v151/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Real Pilot Gate", "real_pilot_gate_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V151Dashboard() {
  return <StageDashboard title="Dummy V151 Real Production Pilot Fire Gate V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v137" summaryFields={summaryFields} />;
}
