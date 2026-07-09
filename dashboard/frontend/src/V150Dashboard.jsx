import StageDashboard from './StageDashboard';

const endpoints = [["Preflight Controller", "/api/v150/preflight-controller"], ["V149 Baseline", "/api/v150/v149-baseline"], ["Authority Intake Readback", "/api/v150/authority-intake-readback"], ["Mode Firewall Readback", "/api/v150/mode-firewall-readback"], ["Rehearsal Readback", "/api/v150/rehearsal-readback"], ["Candidate Proof", "/api/v150/candidate-proof"], ["Limit Only Proof", "/api/v150/limit-only-proof"], ["No Market Order Proof", "/api/v150/no-market-order-proof"], ["Risk Proof", "/api/v150/risk-proof"], ["Abstention Proof", "/api/v150/abstention-proof"], ["Kill Switch Proof", "/api/v150/kill-switch-proof"], ["Rollback Proof", "/api/v150/rollback-proof"], ["Idempotency Proof", "/api/v150/idempotency-proof"], ["Liquidity Slippage Proof", "/api/v150/liquidity-slippage-proof"], ["No Submit Proof", "/api/v150/no-submit-proof"], ["Readiness Governor", "/api/v150/readiness-governor"], ["Execution Lock", "/api/v150/execution-lock"], ["Mission State", "/api/v150/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Preflight", "preflight_controller_status"], ["Preflight Ready", "preflight_ready"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V150Dashboard() {
  return <StageDashboard title="Dummy V150 Real Production Pilot Preflight Packet" endpoints={endpoints} missionKey="dummy_mission_state_report_v136" summaryFields={summaryFields} />;
}
