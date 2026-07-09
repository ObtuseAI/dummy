import StageDashboard from './StageDashboard';

const endpoints = [["Production Lock Controller", "/api/v135/production-lock-controller"], ["V134 Baseline", "/api/v135/v134-baseline"], ["Pilot Status Summary", "/api/v135/pilot-status-summary"], ["Repeat Status Summary", "/api/v135/repeat-status-summary"], ["Scale Status Summary", "/api/v135/scale-status-summary"], ["Controlled Operation Status Summary", "/api/v135/controlled-operation-status-summary"], ["Autonomy Blocker Map", "/api/v135/autonomy-blocker-map"], ["Live Proof Gap Map", "/api/v135/live-proof-gap-map"], ["Risk Proof Gap Map", "/api/v135/risk-proof-gap-map"], ["Abstention Proof Gap Map", "/api/v135/abstention-proof-gap-map"], ["Next Action Matrix", "/api/v135/next-action-matrix"], ["No New Order Proof", "/api/v135/no-new-order-proof"], ["Readiness Governor", "/api/v135/readiness-governor"], ["Execution Lock", "/api/v135/execution-lock"], ["Mission State", "/api/v135/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Production Lock", "production_lock_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V135Dashboard() {
  return <StageDashboard title="Dummy V135 Production Lock Summary & Next-Phase Map" endpoints={endpoints} missionKey="dummy_mission_state_report_v121" summaryFields={summaryFields} />;
}
