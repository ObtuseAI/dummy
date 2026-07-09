import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Forensic Controller", "/api/v120/pilot-forensic-controller"], ["V119 Baseline", "/api/v120/v119-baseline"], ["Order State Parser", "/api/v120/order-state-parser"], ["Fill Reject Cancel Summary", "/api/v120/fill-reject-cancel-summary"], ["Idempotency Check", "/api/v120/idempotency-check"], ["No Repeat Pilot Proof", "/api/v120/no-repeat-pilot-proof"], ["Slippage Latency Fee Buckets", "/api/v120/slippage-latency-fee-buckets"], ["Edge Vs Fill Reality Review", "/api/v120/edge-vs-fill-reality-review"], ["Risk Governor Behavior Review", "/api/v120/risk-governor-behavior-review"], ["Abstention Behavior Review", "/api/v120/abstention-behavior-review"], ["No Private Data Leakage Proof", "/api/v120/no-private-data-leakage-proof"], ["Pilot Autolock", "/api/v120/pilot-autolock"], ["Readiness Governor", "/api/v120/readiness-governor"], ["Execution Lock", "/api/v120/execution-lock"], ["Mission State", "/api/v120/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Forensic", "pilot_forensic_controller_status"], ["Live Orders", "live_orders"], ["Auto-Lock", "pilot_autolock_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V120Dashboard() {
  return <StageDashboard title="Dummy V120 Production Pilot Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v106" summaryFields={summaryFields} />;
}
