import StageDashboard from './StageDashboard';

const endpoints = [["Forensic Controller", "/api/v153/forensic-controller"], ["V152 Baseline", "/api/v153/v152-baseline"], ["Fill Reject Cancel Summary", "/api/v153/fill-reject-cancel-summary"], ["Slippage Bucket", "/api/v153/slippage-bucket"], ["Latency Bucket", "/api/v153/latency-bucket"], ["Fee Bucket", "/api/v153/fee-bucket"], ["Liquidity Reality", "/api/v153/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v153/edge-vs-execution-reality"], ["Abstention Decision Review", "/api/v153/abstention-decision-review"], ["Risk Governor Behavior Review", "/api/v153/risk-governor-behavior-review"], ["Kill Switch Review", "/api/v153/kill-switch-review"], ["Rollback Review", "/api/v153/rollback-review"], ["Private Data Redaction", "/api/v153/private-data-redaction"], ["No New Order Proof", "/api/v153/no-new-order-proof"], ["Readiness Governor", "/api/v153/readiness-governor"], ["Execution Lock", "/api/v153/execution-lock"], ["Mission State", "/api/v153/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Forensic Review", "forensic_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V153Dashboard() {
  return <StageDashboard title="Dummy V153 Real Pilot Forensic Review V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v139" summaryFields={summaryFields} />;
}
