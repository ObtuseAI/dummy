import StageDashboard from './StageDashboard';

const endpoints = [["Risk Stop Policy Controller", "/api/v122/risk-stop-policy-controller"], ["V121 Baseline", "/api/v122/v121-baseline"], ["Stop Loss Lock", "/api/v122/stop-loss-lock"], ["Drift Lock", "/api/v122/drift-lock"], ["Liquidity Lock", "/api/v122/liquidity-lock"], ["Broker Error Lock", "/api/v122/broker-error-lock"], ["Repeated Reject Lock", "/api/v122/repeated-reject-lock"], ["Slippage Lock", "/api/v122/slippage-lock"], ["Session Kill Switch", "/api/v122/session-kill-switch"], ["Daily Lock", "/api/v122/daily-lock"], ["Operator Unlock Requirement", "/api/v122/operator-unlock-requirement"], ["No Order Proof", "/api/v122/no-order-proof"], ["Readiness Governor", "/api/v122/readiness-governor"], ["Execution Lock", "/api/v122/execution-lock"], ["Mission State", "/api/v122/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Risk Stop Policy", "risk_stop_policy_controller_status"], ["Kill Switch", "session_kill_switch_status"], ["Caps Modified", "caps_modified"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V122Dashboard() {
  return <StageDashboard title="Dummy V122 Production Risk & Stop Policy" endpoints={endpoints} missionKey="dummy_mission_state_report_v108" summaryFields={summaryFields} />;
}
