import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Preflight Controller", "/api/v154/repeat-preflight-controller"], ["V153 Baseline", "/api/v154/v153-baseline"], ["Repeat Approval Validator", "/api/v154/repeat-approval-validator"], ["First Pilot Reconcile Prerequisite", "/api/v154/first-pilot-reconcile-prerequisite"], ["First Pilot Forensic Prerequisite", "/api/v154/first-pilot-forensic-prerequisite"], ["No Loss Lock", "/api/v154/no-loss-lock"], ["No Drift Lock", "/api/v154/no-drift-lock"], ["No Liquidity Lock", "/api/v154/no-liquidity-lock"], ["No Broker Error Lock", "/api/v154/no-broker-error-lock"], ["Stricter Risk Threshold", "/api/v154/stricter-risk-threshold"], ["Live Submit Caps Snapshot Recheck", "/api/v154/live-submit-caps-snapshot-recheck"], ["No Auto Repeat Proof", "/api/v154/no-auto-repeat-proof"], ["Readiness Governor", "/api/v154/readiness-governor"], ["Execution Lock", "/api/v154/execution-lock"], ["Mission State", "/api/v154/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Preflight", "repeat_preflight_controller_status"], ["Preflight Ready", "repeat_preflight_ready"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V154Dashboard() {
  return <StageDashboard title="Dummy V154 Repeat Pilot Preflight Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v140" summaryFields={summaryFields} />;
}
