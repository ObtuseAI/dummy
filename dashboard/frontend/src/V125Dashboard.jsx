import StageDashboard from './StageDashboard';

const endpoints = [["Production Lock Controller", "/api/v125/production-lock-controller"], ["V124 Baseline", "/api/v125/v124-baseline"], ["Pilot Status Summary", "/api/v125/pilot-status-summary"], ["Repeat Status Summary", "/api/v125/repeat-status-summary"], ["Scale Status Summary", "/api/v125/scale-status-summary"], ["Controlled Operation Status Summary", "/api/v125/controlled-operation-status-summary"], ["Autonomy Blocker Map", "/api/v125/autonomy-blocker-map"], ["Live Proof Gap Map", "/api/v125/live-proof-gap-map"], ["Risk Proof Gap Map", "/api/v125/risk-proof-gap-map"], ["Abstention Proof Gap Map", "/api/v125/abstention-proof-gap-map"], ["Next Action Matrix", "/api/v125/next-action-matrix"], ["No New Order Proof", "/api/v125/no-new-order-proof"], ["Readiness Governor", "/api/v125/readiness-governor"], ["Execution Lock", "/api/v125/execution-lock"], ["Mission State", "/api/v125/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Production Lock", "production_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V125Dashboard() {
  return <StageDashboard title="Dummy V125 Production Lock & Next-Phase Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v111" summaryFields={summaryFields} />;
}
