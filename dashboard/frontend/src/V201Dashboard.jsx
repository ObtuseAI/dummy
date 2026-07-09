import StageDashboard from './StageDashboard';

const endpoints = [["Forensic Controller", "/api/v201/forensic-controller"], ["V200 Baseline", "/api/v201/v200-baseline"], ["Fill Reject Cancel Summary", "/api/v201/fill-reject-cancel-summary"], ["Proof Target Summary", "/api/v201/proof-target-summary"], ["Slippage Bucket", "/api/v201/slippage-bucket"], ["Latency Bucket", "/api/v201/latency-bucket"], ["Fee Bucket", "/api/v201/fee-bucket"], ["Liquidity Reality", "/api/v201/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v201/edge-vs-execution-reality"], ["Abstention Decision Review", "/api/v201/abstention-decision-review"], ["Risk Governor Behavior Review", "/api/v201/risk-governor-behavior-review"], ["Kill Switch Review", "/api/v201/kill-switch-review"], ["Rollback Review", "/api/v201/rollback-review"], ["Broker Readonly Consistency Check", "/api/v201/broker-readonly-consistency-check"], ["Private Data Redaction", "/api/v201/private-data-redaction"], ["No New Order Proof", "/api/v201/no-new-order-proof"], ["Readiness Governor", "/api/v201/readiness-governor"], ["Execution Lock", "/api/v201/execution-lock"], ["Mission State", "/api/v201/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Forensic Review", "forensic_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V201Dashboard() {
  return <StageDashboard title="Dummy V201 First Live-Proof Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v187" summaryFields={summaryFields} />;
}
