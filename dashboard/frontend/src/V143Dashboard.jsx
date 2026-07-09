import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Eligibility Controller", "/api/v143/repeat-eligibility-controller"], ["V142 Baseline", "/api/v143/v142-baseline"], ["Repeat Pilot Approval Validator", "/api/v143/repeat-pilot-approval-validator"], ["First Pilot Reconcile Prerequisite", "/api/v143/first-pilot-reconcile-prerequisite"], ["First Pilot Forensic Prerequisite", "/api/v143/first-pilot-forensic-prerequisite"], ["No Loss Lock", "/api/v143/no-loss-lock"], ["No Drift Lock", "/api/v143/no-drift-lock"], ["No Liquidity Lock", "/api/v143/no-liquidity-lock"], ["No Broker Error Lock", "/api/v143/no-broker-error-lock"], ["Risk Threshold Prerequisite", "/api/v143/risk-threshold-prerequisite"], ["Live Submit Caps Control Proof", "/api/v143/live-submit-caps-control-proof"], ["No Auto Repeat Proof", "/api/v143/no-auto-repeat-proof"], ["Readiness Governor", "/api/v143/readiness-governor"], ["Execution Lock", "/api/v143/execution-lock"], ["Mission State", "/api/v143/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Eligibility", "repeat_eligibility_controller_status"], ["Recommendation", "repeat_pilot_recommendation"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V143Dashboard() {
  return <StageDashboard title="Dummy V143 Repeat Pilot Approval & Eligibility Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v129" summaryFields={summaryFields} />;
}
