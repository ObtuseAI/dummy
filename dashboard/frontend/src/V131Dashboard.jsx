import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Pilot Gate Controller", "/api/v131/repeat-pilot-gate-controller"], ["V130 Baseline", "/api/v131/v130-baseline"], ["Repeat Pilot Approval Validator", "/api/v131/repeat-pilot-approval-validator"], ["First Pilot Forensic Prerequisite", "/api/v131/first-pilot-forensic-prerequisite"], ["No Loss Lock", "/api/v131/no-loss-lock"], ["No Drift Lock", "/api/v131/no-drift-lock"], ["No Liquidity Lock", "/api/v131/no-liquidity-lock"], ["Risk Threshold Prerequisite", "/api/v131/risk-threshold-prerequisite"], ["Live Submit Caps Control Proof", "/api/v131/live-submit-caps-control-proof"], ["No Auto Repeat Proof", "/api/v131/no-auto-repeat-proof"], ["Readiness Governor", "/api/v131/readiness-governor"], ["Execution Lock", "/api/v131/execution-lock"], ["Mission State", "/api/v131/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"], ["Recommendation", "repeat_pilot_recommendation"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V131Dashboard() {
  return <StageDashboard title="Dummy V131 Repeat Production Pilot Review Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v117" summaryFields={summaryFields} />;
}
