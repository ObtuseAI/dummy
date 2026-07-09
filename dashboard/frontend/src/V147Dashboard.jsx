import StageDashboard from './StageDashboard';

const endpoints = [["Intake Validator Controller", "/api/v147/intake-validator-controller"], ["V146 Baseline", "/api/v147/v146-baseline"], ["Production Pilot Approval Validator", "/api/v147/production-pilot-approval-validator"], ["Broker Readonly Approval Validator", "/api/v147/broker-readonly-approval-validator"], ["Live Submit Readonly Checker", "/api/v147/live-submit-readonly-checker"], ["Caps Readonly Checker", "/api/v147/caps-readonly-checker"], ["Firewall Adapter Checker", "/api/v147/firewall-adapter-checker"], ["Config Hash Snapshot", "/api/v147/config-hash-snapshot"], ["Caps Hash Snapshot", "/api/v147/caps-hash-snapshot"], ["Secret Redaction", "/api/v147/secret-redaction"], ["No Submit Proof", "/api/v147/no-submit-proof"], ["No Caps Modification Proof", "/api/v147/no-caps-modification-proof"], ["Readiness Governor", "/api/v147/readiness-governor"], ["Execution Lock", "/api/v147/execution-lock"], ["Mission State", "/api/v147/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Intake Validator", "intake_validator_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V147Dashboard() {
  return <StageDashboard title="Dummy V147 Real Authority Intake Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v133" summaryFields={summaryFields} />;
}
