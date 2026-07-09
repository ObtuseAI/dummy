import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Pair Audit Controller", "/api/v170/pilot-pair-audit-controller"], ["V169 Baseline", "/api/v170/v169-baseline"], ["First Pilot Proof Readback", "/api/v170/first-pilot-proof-readback"], ["Repeat Pilot Proof Readback", "/api/v170/repeat-pilot-proof-readback"], ["Fill Quality Comparison", "/api/v170/fill-quality-comparison"], ["Latency Comparison", "/api/v170/latency-comparison"], ["Slippage Comparison", "/api/v170/slippage-comparison"], ["Fee Comparison", "/api/v170/fee-comparison"], ["Edge Stability Review", "/api/v170/edge-stability-review"], ["Abstention Quality Review", "/api/v170/abstention-quality-review"], ["Risk Stop Review", "/api/v170/risk-stop-review"], ["No Submit Proof", "/api/v170/no-submit-proof"], ["No Scale Proof", "/api/v170/no-scale-proof"], ["Readiness Governor", "/api/v170/readiness-governor"], ["Execution Lock", "/api/v170/execution-lock"], ["Mission State", "/api/v170/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pilot Pair Audit", "pilot_pair_audit_controller_status"], ["Decision", "pair_decision"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V170Dashboard() {
  return <StageDashboard title="Dummy V170 Pilot Pair Performance Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v156" summaryFields={summaryFields} />;
}
