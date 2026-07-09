import StageDashboard from './StageDashboard';

const endpoints = [["Authority Resolver Controller", "/api/v208/authority-resolver-controller"], ["V207 Baseline", "/api/v208/v207-baseline"], ["Exact Approval Check", "/api/v208/exact-approval-check"], ["Config Caps Quorum Check", "/api/v208/config-caps-quorum-check"], ["Firewall Adapter Check", "/api/v208/firewall-adapter-check"], ["Broker Readonly Check", "/api/v208/broker-readonly-check"], ["Candidate Risk Abstention Check", "/api/v208/candidate-risk-abstention-check"], ["Mode Firewall Check", "/api/v208/mode-firewall-check"], ["Idempotency Check", "/api/v208/idempotency-check"], ["Proof Lock Check", "/api/v208/proof-lock-check"], ["Authority State", "/api/v208/authority-state"], ["No Submit Proof", "/api/v208/no-submit-proof"], ["No Broker Contact Default Proof", "/api/v208/no-broker-contact-default-proof"], ["Readiness Governor", "/api/v208/readiness-governor"], ["Execution Lock", "/api/v208/execution-lock"], ["Mission State", "/api/v208/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Authority Resolver", "authority_resolver_controller_status"], ["Authority State", "authority_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V208Dashboard() {
  return <StageDashboard title="Dummy V208 Dry/Live Authority Resolver" endpoints={endpoints} missionKey="dummy_mission_state_report_v194" summaryFields={summaryFields} />;
}
