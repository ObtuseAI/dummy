import StageDashboard from './StageDashboard';

const endpoints = [["Forensic Controller", "/api/v163/forensic-controller"], ["V162 Baseline", "/api/v163/v162-baseline"], ["Fill Reject Cancel Summary", "/api/v163/fill-reject-cancel-summary"], ["Slippage Bucket", "/api/v163/slippage-bucket"], ["Latency Bucket", "/api/v163/latency-bucket"], ["Fee Bucket", "/api/v163/fee-bucket"], ["Liquidity Reality", "/api/v163/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v163/edge-vs-execution-reality"], ["Abstention Decision Review", "/api/v163/abstention-decision-review"], ["Risk Governor Behavior Review", "/api/v163/risk-governor-behavior-review"], ["Kill Switch Review", "/api/v163/kill-switch-review"], ["Rollback Review", "/api/v163/rollback-review"], ["Broker Readonly Consistency Check", "/api/v163/broker-readonly-consistency-check"], ["Private Data Redaction", "/api/v163/private-data-redaction"], ["No New Order Proof", "/api/v163/no-new-order-proof"], ["Readiness Governor", "/api/v163/readiness-governor"], ["Execution Lock", "/api/v163/execution-lock"], ["Mission State", "/api/v163/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Forensic Review", "forensic_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V163Dashboard() {
  return <StageDashboard title="Dummy V163 First Real Pilot Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v149" summaryFields={summaryFields} />;
}
