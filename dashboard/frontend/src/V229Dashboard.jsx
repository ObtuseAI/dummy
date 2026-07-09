import StageDashboard from './StageDashboard';

const endpoints = [["Final Resolver Arming Controller", "/api/v229/final-resolver-arming-controller"], ["V228 Baseline", "/api/v229/v228-baseline"], ["Resolver State Readback", "/api/v229/resolver-state-readback"], ["Intake Valid Quorum", "/api/v229/intake-valid-quorum"], ["Config Caps Immutable Quorum", "/api/v229/config-caps-immutable-quorum"], ["Firewall Adapter Proof", "/api/v229/firewall-adapter-proof"], ["Dry Pipeline Proof", "/api/v229/dry-pipeline-proof"], ["Kill Switch Proof", "/api/v229/kill-switch-proof"], ["Rollback Proof", "/api/v229/rollback-proof"], ["Idempotency Proof", "/api/v229/idempotency-proof"], ["One Attempt Proof", "/api/v229/one-attempt-proof"], ["No Market Order Proof", "/api/v229/no-market-order-proof"], ["Mode Live Authorized Proof", "/api/v229/mode-live-authorized-proof"], ["Env Gate Check", "/api/v229/env-gate-check"], ["No Submit Proof", "/api/v229/no-submit-proof"], ["Readiness Governor", "/api/v229/readiness-governor"], ["Execution Lock", "/api/v229/execution-lock"], ["Mission State", "/api/v229/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Resolver Arming", "final_resolver_arming_controller_status"], ["Arming Ready", "arming_ready"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V229Dashboard() {
  return <StageDashboard title="Dummy V229 Final Resolver Arming Orchestrator No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v215" summaryFields={summaryFields} />;
}
