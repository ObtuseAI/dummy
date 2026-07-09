import StageDashboard from './StageDashboard';

const endpoints = [["Zero Broker Dry Validation Controller", "/api/v217/zero-broker-dry-validation-controller"], ["V216 Baseline", "/api/v217/v216-baseline"], ["Dry Mode Authority Resolver Run", "/api/v217/dry-mode-authority-resolver-run"], ["Candidate Risk Abstention Checks", "/api/v217/candidate-risk-abstention-checks"], ["Proof Target Validation", "/api/v217/proof-target-validation"], ["Simulated Idempotency Key", "/api/v217/simulated-idempotency-key"], ["Simulated Proof Lock", "/api/v217/simulated-proof-lock"], ["Simulated Reconcile Schema", "/api/v217/simulated-reconcile-schema"], ["Simulated Forensic Schema", "/api/v217/simulated-forensic-schema"], ["No Firewall Submit Proof", "/api/v217/no-firewall-submit-proof"], ["No Broker Payload Proof", "/api/v217/no-broker-payload-proof"], ["No Account Access Proof", "/api/v217/no-account-access-proof"], ["No File Write Proof", "/api/v217/no-file-write-proof"], ["Readiness Governor", "/api/v217/readiness-governor"], ["Execution Lock", "/api/v217/execution-lock"], ["Mission State", "/api/v217/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry Validation", "zero_broker_dry_validation_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V217Dashboard() {
  return <StageDashboard title="Dummy V217 Zero Broker Dry Validation Full Path No Contact" endpoints={endpoints} missionKey="dummy_mission_state_report_v203" summaryFields={summaryFields} />;
}
