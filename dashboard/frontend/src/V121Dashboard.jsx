import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Pilot Gate Controller", "/api/v121/repeat-pilot-gate-controller"], ["V120 Baseline", "/api/v121/v120-baseline"], ["Repeat Pilot Approval Validator", "/api/v121/repeat-pilot-approval-validator"], ["First Pilot Forensic Prerequisite", "/api/v121/first-pilot-forensic-prerequisite"], ["No Loss Lock", "/api/v121/no-loss-lock"], ["No Drift Lock", "/api/v121/no-drift-lock"], ["Risk Threshold Prerequisite", "/api/v121/risk-threshold-prerequisite"], ["Live Submit Caps Control Proof", "/api/v121/live-submit-caps-control-proof"], ["No Auto Repeat Proof", "/api/v121/no-auto-repeat-proof"], ["Readiness Governor", "/api/v121/readiness-governor"], ["Execution Lock", "/api/v121/execution-lock"], ["Mission State", "/api/v121/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"], ["Recommendation", "repeat_pilot_recommendation"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V121Dashboard() {
  return <StageDashboard title="Dummy V121 Repeat Production Pilot Review Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v107" summaryFields={summaryFields} />;
}
