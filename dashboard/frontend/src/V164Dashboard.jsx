import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Eligibility Controller", "/api/v164/repeat-eligibility-controller"], ["V163 Baseline", "/api/v164/v163-baseline"], ["Repeat Approval Validator", "/api/v164/repeat-approval-validator"], ["First Pilot Reconcile Prerequisite", "/api/v164/first-pilot-reconcile-prerequisite"], ["First Pilot Forensic Prerequisite", "/api/v164/first-pilot-forensic-prerequisite"], ["No Loss Lock", "/api/v164/no-loss-lock"], ["No Drift Lock", "/api/v164/no-drift-lock"], ["No Liquidity Lock", "/api/v164/no-liquidity-lock"], ["No Broker Error Lock", "/api/v164/no-broker-error-lock"], ["No Slippage Lock", "/api/v164/no-slippage-lock"], ["Risk Threshold Prerequisite", "/api/v164/risk-threshold-prerequisite"], ["Abstention Quality Prerequisite", "/api/v164/abstention-quality-prerequisite"], ["Live Submit Caps Unchanged Proof", "/api/v164/live-submit-caps-unchanged-proof"], ["No Auto Repeat Proof", "/api/v164/no-auto-repeat-proof"], ["No Submit Proof", "/api/v164/no-submit-proof"], ["Readiness Governor", "/api/v164/readiness-governor"], ["Execution Lock", "/api/v164/execution-lock"], ["Mission State", "/api/v164/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Eligibility", "repeat_eligibility_controller_status"], ["Decision", "eligibility_decision"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V164Dashboard() {
  return <StageDashboard title="Dummy V164 Repeat-Pilot Eligibility Decision" endpoints={endpoints} missionKey="dummy_mission_state_report_v150" summaryFields={summaryFields} />;
}
