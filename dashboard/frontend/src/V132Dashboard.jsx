import StageDashboard from './StageDashboard';

const endpoints = [["Risk Stop Policy Controller", "/api/v132/risk-stop-policy-controller"], ["V131 Baseline", "/api/v132/v131-baseline"], ["Stop Loss Lock", "/api/v132/stop-loss-lock"], ["Drift Lock", "/api/v132/drift-lock"], ["Liquidity Lock", "/api/v132/liquidity-lock"], ["Broker Error Lock", "/api/v132/broker-error-lock"], ["Repeated Reject Lock", "/api/v132/repeated-reject-lock"], ["Slippage Lock", "/api/v132/slippage-lock"], ["Session Kill Switch", "/api/v132/session-kill-switch"], ["Daily Lock", "/api/v132/daily-lock"], ["Operator Unlock Requirement", "/api/v132/operator-unlock-requirement"], ["No Order Proof", "/api/v132/no-order-proof"], ["Readiness Governor", "/api/v132/readiness-governor"], ["Execution Lock", "/api/v132/execution-lock"], ["Mission State", "/api/v132/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Risk Stop Policy", "risk_stop_policy_controller_status"], ["Kill Switch", "session_kill_switch_status"], ["Caps Modified", "caps_modified"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V132Dashboard() {
  return <StageDashboard title="Dummy V132 Production Risk & Stop Policy V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v118" summaryFields={summaryFields} />;
}
