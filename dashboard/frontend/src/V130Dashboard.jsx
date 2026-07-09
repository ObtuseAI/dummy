import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Reconcile Controller", "/api/v130/pilot-reconcile-controller"], ["V129 Baseline", "/api/v130/v129-baseline"], ["Order State Parser", "/api/v130/order-state-parser"], ["Fill Reject Cancel Summary", "/api/v130/fill-reject-cancel-summary"], ["Idempotency Check", "/api/v130/idempotency-check"], ["No Repeat Pilot Proof", "/api/v130/no-repeat-pilot-proof"], ["Slippage Latency Fee Buckets", "/api/v130/slippage-latency-fee-buckets"], ["Edge Vs Fill Reality Review", "/api/v130/edge-vs-fill-reality-review"], ["Risk Governor Behavior Review", "/api/v130/risk-governor-behavior-review"], ["Abstention Behavior Review", "/api/v130/abstention-behavior-review"], ["No Private Data Leakage Proof", "/api/v130/no-private-data-leakage-proof"], ["Pilot Autolock", "/api/v130/pilot-autolock"], ["Readiness Governor", "/api/v130/readiness-governor"], ["Execution Lock", "/api/v130/execution-lock"], ["Mission State", "/api/v130/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Reconcile", "pilot_reconcile_controller_status"], ["Live Orders", "live_orders"], ["Auto-Lock", "pilot_autolock_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V130Dashboard() {
  return <StageDashboard title="Dummy V130 Production Pilot Reconcile & Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v116" summaryFields={summaryFields} />;
}
