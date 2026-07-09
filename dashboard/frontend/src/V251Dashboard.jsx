import StageDashboard from './StageDashboard';

const endpoints = [["Pre Execution Freeze Controller", "/api/v251/pre-execution-freeze-controller"], ["V250 Baseline", "/api/v251/v250-baseline"], ["Freeze Snapshot", "/api/v251/freeze-snapshot"], ["Manifest Hash", "/api/v251/manifest-hash"], ["Live Submit Hash", "/api/v251/live-submit-hash"], ["Caps Hash", "/api/v251/caps-hash"], ["Adapter Descriptor Hash", "/api/v251/adapter-descriptor-hash"], ["Env Gate Presence", "/api/v251/env-gate-presence"], ["Resolver State", "/api/v251/resolver-state"], ["Proof Lock Status", "/api/v251/proof-lock-status"], ["No Submit Proof", "/api/v251/no-submit-proof"], ["No Broker Contact Proof", "/api/v251/no-broker-contact-proof"], ["No Mutation Proof", "/api/v251/no-mutation-proof"], ["Readiness Governor", "/api/v251/readiness-governor"], ["Execution Lock", "/api/v251/execution-lock"], ["Mission State", "/api/v251/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Freeze Report", "pre_execution_freeze_controller_status"], ["Resolver State", "resolver_state"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V251Dashboard() {
  return <StageDashboard title="Dummy V251 Pre Execution Freeze Report No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v237" summaryFields={summaryFields} />;
}
