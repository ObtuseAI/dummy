import StageDashboard from './StageDashboard';

const endpoints = [["Forensic Spine V2 Controller", "/api/v221/forensic-spine-v2-controller"], ["V220 Baseline", "/api/v221/v220-baseline"], ["Fill Reject Cancel Summary", "/api/v221/fill-reject-cancel-summary"], ["Proof Target Summary", "/api/v221/proof-target-summary"], ["Slippage Bucket", "/api/v221/slippage-bucket"], ["Latency Bucket", "/api/v221/latency-bucket"], ["Fee Bucket", "/api/v221/fee-bucket"], ["Liquidity Reality", "/api/v221/liquidity-reality"], ["Edge Vs Execution Reality", "/api/v221/edge-vs-execution-reality"], ["Risk Behavior", "/api/v221/risk-behavior"], ["Abstention Behavior", "/api/v221/abstention-behavior"], ["Kill Switch Behavior", "/api/v221/kill-switch-behavior"], ["Rollback Behavior", "/api/v221/rollback-behavior"], ["Broker Readonly Consistency", "/api/v221/broker-readonly-consistency"], ["No New Order Proof", "/api/v221/no-new-order-proof"], ["Readiness Governor", "/api/v221/readiness-governor"], ["Execution Lock", "/api/v221/execution-lock"], ["Mission State", "/api/v221/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Forensic Spine", "forensic_spine_v2_controller_status"], ["Order State", "order_state"], ["New Order Placed", "new_order_placed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V221Dashboard() {
  return <StageDashboard title="Dummy V221 Forensic Spine V2 Proof Reality Risk And Abstention Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v207" summaryFields={summaryFields} />;
}
