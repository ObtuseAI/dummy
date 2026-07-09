import StageDashboard from './StageDashboard';

const endpoints = [["Session Forensic Controller", "/api/v179/session-forensic-controller"], ["V178 Baseline", "/api/v179/v178-baseline"], ["Fill Reject Cancel Summary", "/api/v179/fill-reject-cancel-summary"], ["Slippage Buckets", "/api/v179/slippage-buckets"], ["Latency Buckets", "/api/v179/latency-buckets"], ["Fee Buckets", "/api/v179/fee-buckets"], ["Liquidity Reality", "/api/v179/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v179/edge-vs-execution-reality"], ["Per Order Abstention Review", "/api/v179/per-order-abstention-review"], ["Risk Governor Behavior Review", "/api/v179/risk-governor-behavior-review"], ["Kill Switch Review", "/api/v179/kill-switch-review"], ["Rollback Review", "/api/v179/rollback-review"], ["Broker Readonly Consistency Check", "/api/v179/broker-readonly-consistency-check"], ["Private Data Redaction", "/api/v179/private-data-redaction"], ["No New Order Proof", "/api/v179/no-new-order-proof"], ["Readiness Governor", "/api/v179/readiness-governor"], ["Execution Lock", "/api/v179/execution-lock"], ["Mission State", "/api/v179/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Forensic", "session_forensic_controller_status"], ["Live Orders", "live_orders"], ["Edge vs Execution", "edge_vs_execution_reality_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V179Dashboard() {
  return <StageDashboard title="Dummy V179 Controlled Session Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v165" summaryFields={summaryFields} />;
}
