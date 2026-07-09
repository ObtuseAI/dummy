import StageDashboard from './StageDashboard';

const endpoints = [["Final Live Proof Arming Check Controller", "/api/v218/final-live-proof-arming-check-controller"], ["V217 Baseline", "/api/v218/v217-baseline"], ["Config Caps Immutable Quorum", "/api/v218/config-caps-immutable-quorum"], ["Firewall Adapter Proof", "/api/v218/firewall-adapter-proof"], ["Broker Readonly Proof", "/api/v218/broker-readonly-proof"], ["Dry Validation Proof", "/api/v218/dry-validation-proof"], ["Kill Switch Proof", "/api/v218/kill-switch-proof"], ["Rollback Proof", "/api/v218/rollback-proof"], ["Idempotency Proof", "/api/v218/idempotency-proof"], ["One Attempt Proof", "/api/v218/one-attempt-proof"], ["No Market Order Proof", "/api/v218/no-market-order-proof"], ["Mode Live Authorized Proof", "/api/v218/mode-live-authorized-proof"], ["Env Gate Check", "/api/v218/env-gate-check"], ["No Submit Proof", "/api/v218/no-submit-proof"], ["Readiness Governor", "/api/v218/readiness-governor"], ["Execution Lock", "/api/v218/execution-lock"], ["Mission State", "/api/v218/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Arming Check", "final_live_proof_arming_check_controller_status"], ["Arming Ready", "arming_ready"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V218Dashboard() {
  return <StageDashboard title="Dummy V218 Final Live Proof Arming Check No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v204" summaryFields={summaryFields} />;
}
