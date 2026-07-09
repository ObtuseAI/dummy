import StageDashboard from './StageDashboard';

const endpoints = [["Forensic Runner Controller", "/api/v211/forensic-runner-controller"], ["V210 Baseline", "/api/v211/v210-baseline"], ["Fill Reject Cancel Summary", "/api/v211/fill-reject-cancel-summary"], ["Slippage Bucket", "/api/v211/slippage-bucket"], ["Latency Bucket", "/api/v211/latency-bucket"], ["Fee Bucket", "/api/v211/fee-bucket"], ["Liquidity Reality", "/api/v211/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v211/edge-vs-execution-reality"], ["Risk Behavior", "/api/v211/risk-behavior"], ["Abstention Behavior", "/api/v211/abstention-behavior"], ["Kill Switch Behavior", "/api/v211/kill-switch-behavior"], ["Rollback Behavior", "/api/v211/rollback-behavior"], ["Broker Readonly Consistency Check", "/api/v211/broker-readonly-consistency-check"], ["Private Data Redaction", "/api/v211/private-data-redaction"], ["No New Order Proof", "/api/v211/no-new-order-proof"], ["Readiness Governor", "/api/v211/readiness-governor"], ["Execution Lock", "/api/v211/execution-lock"], ["Mission State", "/api/v211/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Forensic Runner", "forensic_runner_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V211Dashboard() {
  return <StageDashboard title="Dummy V211 Forensic Runner Spine" endpoints={endpoints} missionKey="dummy_mission_state_report_v197" summaryFields={summaryFields} />;
}
