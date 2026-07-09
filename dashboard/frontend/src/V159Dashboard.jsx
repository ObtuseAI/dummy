import StageDashboard from './StageDashboard';

const endpoints = [["Broker Readonly Controller", "/api/v159/broker-readonly-controller"], ["V158 Baseline", "/api/v159/v158-baseline"], ["Broker Readonly Approval Validator", "/api/v159/broker-readonly-approval-validator"], ["Readonly Adapter Capability Check", "/api/v159/readonly-adapter-capability-check"], ["Allowed Readonly Calls List", "/api/v159/allowed-readonly-calls-list"], ["Forbidden Calls List", "/api/v159/forbidden-calls-list"], ["Secret Redaction", "/api/v159/secret-redaction"], ["Account Private Data Minimization", "/api/v159/account-private-data-minimization"], ["No Submit Cancel Proof", "/api/v159/no-submit-cancel-proof"], ["No Private Data Leakage Proof", "/api/v159/no-private-data-leakage-proof"], ["Readiness Governor", "/api/v159/readiness-governor"], ["Execution Lock", "/api/v159/execution-lock"], ["Mission State", "/api/v159/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Broker Read-Only", "broker_readonly_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V159Dashboard() {
  return <StageDashboard title="Dummy V159 Broker Read-Only Verification" endpoints={endpoints} missionKey="dummy_mission_state_report_v145" summaryFields={summaryFields} />;
}
