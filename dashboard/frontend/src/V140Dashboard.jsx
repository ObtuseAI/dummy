import StageDashboard from './StageDashboard';

const endpoints = [["Final Auth Packet Controller", "/api/v140/final-auth-packet-controller"], ["V139 Baseline", "/api/v140/v139-baseline"], ["Authority Binder Readback", "/api/v140/authority-binder-readback"], ["Live Submit Caps Snapshot Readback", "/api/v140/live-submit-caps-snapshot-readback"], ["Firewall Contract Readback", "/api/v140/firewall-contract-readback"], ["Candidate Abstention Readback", "/api/v140/candidate-abstention-readback"], ["Exact Pilot Approval Proof", "/api/v140/exact-pilot-approval-proof"], ["Limit Only Proof", "/api/v140/limit-only-proof"], ["No Market Order Proof", "/api/v140/no-market-order-proof"], ["Kill Switch Proof", "/api/v140/kill-switch-proof"], ["Rollback Proof", "/api/v140/rollback-proof"], ["Idempotency Proof", "/api/v140/idempotency-proof"], ["Liquidity Slippage Proof", "/api/v140/liquidity-slippage-proof"], ["One Pilot Only Proof", "/api/v140/one-pilot-only-proof"], ["No Submit Proof", "/api/v140/no-submit-proof"], ["Readiness Governor", "/api/v140/readiness-governor"], ["Execution Lock", "/api/v140/execution-lock"], ["Mission State", "/api/v140/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Final Auth Packet", "final_auth_packet_controller_status"], ["Packet Ready", "auth_packet_ready"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V140Dashboard() {
  return <StageDashboard title="Dummy V140 Final Production Pilot Authorization Packet" endpoints={endpoints} missionKey="dummy_mission_state_report_v126" summaryFields={summaryFields} />;
}
