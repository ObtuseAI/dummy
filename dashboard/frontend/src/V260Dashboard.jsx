import StageDashboard from './StageDashboard';

const endpoints = [["Pre Execution Freeze V2 Controller", "/api/v260/pre-execution-freeze-v2-controller"], ["V259 Baseline", "/api/v260/v259-baseline"], ["Freeze Snapshot", "/api/v260/freeze-snapshot"], ["Approval Hash Ledger", "/api/v260/approval-hash-ledger"], ["Config Hash Capture", "/api/v260/config-hash-capture"], ["Adapter Descriptor Hash", "/api/v260/adapter-descriptor-hash"], ["Env Gate Presence", "/api/v260/env-gate-presence"], ["Resolver State", "/api/v260/resolver-state"], ["Market Order Denial", "/api/v260/market-order-denial"], ["No Submit Proof", "/api/v260/no-submit-proof"], ["No Broker Contact Proof", "/api/v260/no-broker-contact-proof"], ["No Mutation Proof", "/api/v260/no-mutation-proof"], ["Readiness Governor", "/api/v260/readiness-governor"], ["Execution Lock", "/api/v260/execution-lock"], ["Mission State", "/api/v260/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Freeze V2", "pre_execution_freeze_v2_controller_status"], ["Resolver State", "resolver_state"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V260Dashboard() {
  return <StageDashboard title="Dummy V260 Pre Execution Freeze V2 Armable Snapshot No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v246" summaryFields={summaryFields} />;
}
