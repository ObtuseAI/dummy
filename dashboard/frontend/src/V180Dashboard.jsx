import StageDashboard from './StageDashboard';

const endpoints = [["Session Decision Controller", "/api/v180/session-decision-controller"], ["V179 Baseline", "/api/v180/v179-baseline"], ["Session Reconcile Prerequisite", "/api/v180/session-reconcile-prerequisite"], ["Session Forensic Prerequisite", "/api/v180/session-forensic-prerequisite"], ["No Loss Lock", "/api/v180/no-loss-lock"], ["No Drift Lock", "/api/v180/no-drift-lock"], ["No Liquidity Lock", "/api/v180/no-liquidity-lock"], ["No Broker Error Lock", "/api/v180/no-broker-error-lock"], ["No Slippage Lock", "/api/v180/no-slippage-lock"], ["Risk Threshold Review", "/api/v180/risk-threshold-review"], ["Abstention Quality Review", "/api/v180/abstention-quality-review"], ["No Submit Proof", "/api/v180/no-submit-proof"], ["No Scale Proof", "/api/v180/no-scale-proof"], ["No Autonomy Proof", "/api/v180/no-autonomy-proof"], ["Readiness Governor", "/api/v180/readiness-governor"], ["Execution Lock", "/api/v180/execution-lock"], ["Mission State", "/api/v180/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Decision", "session_decision_controller_status"], ["Decision", "session_decision"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V180Dashboard() {
  return <StageDashboard title="Dummy V180 Session Stop/Repeat/Repair Decision" endpoints={endpoints} missionKey="dummy_mission_state_report_v166" summaryFields={summaryFields} />;
}
