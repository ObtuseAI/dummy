import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Forensic Controller", "/api/v169/repeat-forensic-controller"], ["V168 Baseline", "/api/v169/v168-baseline"], ["Fill Reject Cancel Summary", "/api/v169/fill-reject-cancel-summary"], ["Slippage Bucket", "/api/v169/slippage-bucket"], ["Latency Bucket", "/api/v169/latency-bucket"], ["Fee Bucket", "/api/v169/fee-bucket"], ["Liquidity Reality", "/api/v169/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v169/edge-vs-execution-reality"], ["Abstention Decision Review", "/api/v169/abstention-decision-review"], ["Risk Governor Behavior Review", "/api/v169/risk-governor-behavior-review"], ["Kill Switch Review", "/api/v169/kill-switch-review"], ["Rollback Review", "/api/v169/rollback-review"], ["Broker Readonly Consistency Check", "/api/v169/broker-readonly-consistency-check"], ["Private Data Redaction", "/api/v169/private-data-redaction"], ["No New Order Proof", "/api/v169/no-new-order-proof"], ["Readiness Governor", "/api/v169/readiness-governor"], ["Execution Lock", "/api/v169/execution-lock"], ["Mission State", "/api/v169/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Forensic", "repeat_forensic_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V169Dashboard() {
  return <StageDashboard title="Dummy V169 Repeat Pilot Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v155" summaryFields={summaryFields} />;
}
