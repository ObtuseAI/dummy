import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Auth Packet Controller", "/api/v128/pilot-auth-packet-controller"], ["V127 Baseline", "/api/v128/v127-baseline"], ["Candidate Abstention Proof", "/api/v128/candidate-abstention-proof"], ["Risk Policy Proof", "/api/v128/risk-policy-proof"], ["Controlled Operation Gate Proof", "/api/v128/controlled-operation-gate-proof"], ["Live Submit Caps Firewall Tieout", "/api/v128/live-submit-caps-firewall-tieout"], ["Limit Only Proof", "/api/v128/limit-only-proof"], ["No Market Order Proof", "/api/v128/no-market-order-proof"], ["Liquidity Slippage Proof", "/api/v128/liquidity-slippage-proof"], ["Kill Switch Proof", "/api/v128/kill-switch-proof"], ["Rollback Proof", "/api/v128/rollback-proof"], ["Idempotency Proof", "/api/v128/idempotency-proof"], ["No Submit Proof", "/api/v128/no-submit-proof"], ["Readiness Governor", "/api/v128/readiness-governor"], ["Execution Lock", "/api/v128/execution-lock"], ["Mission State", "/api/v128/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Auth Packet", "pilot_auth_packet_controller_status"], ["Packet Ready", "auth_packet_ready"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V128Dashboard() {
  return <StageDashboard title="Dummy V128 Production Pilot Final Authorization Packet" endpoints={endpoints} missionKey="dummy_mission_state_report_v114" summaryFields={summaryFields} />;
}
