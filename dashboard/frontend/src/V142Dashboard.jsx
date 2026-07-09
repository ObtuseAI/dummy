import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Reconcile Controller", "/api/v142/pilot-reconcile-controller"], ["V141 Baseline", "/api/v142/v141-baseline"], ["Order State Parser", "/api/v142/order-state-parser"], ["Fill Reject Cancel Summary", "/api/v142/fill-reject-cancel-summary"], ["Idempotency Check", "/api/v142/idempotency-check"], ["No Repeat Pilot Proof", "/api/v142/no-repeat-pilot-proof"], ["Slippage Latency Fee Buckets", "/api/v142/slippage-latency-fee-buckets"], ["Edge Vs Fill Reality Review", "/api/v142/edge-vs-fill-reality-review"], ["Abstention Quality Review", "/api/v142/abstention-quality-review"], ["Risk Governor Behavior Review", "/api/v142/risk-governor-behavior-review"], ["No Private Data Leakage Proof", "/api/v142/no-private-data-leakage-proof"], ["Pilot Autolock", "/api/v142/pilot-autolock"], ["Readiness Governor", "/api/v142/readiness-governor"], ["Execution Lock", "/api/v142/execution-lock"], ["Mission State", "/api/v142/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Reconcile", "pilot_reconcile_controller_status"], ["Live Orders", "live_orders"], ["Auto-Lock", "pilot_autolock_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V142Dashboard() {
  return <StageDashboard title="Dummy V142 Production Pilot Reconcile & Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v128" summaryFields={summaryFields} />;
}
