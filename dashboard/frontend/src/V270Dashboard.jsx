import StageDashboard from './StageDashboard';

const endpoints = [["Broker Readonly Optional Verifier Controller", "/api/v270/broker-readonly-optional-verifier-controller"], ["V269 Baseline", "/api/v270/v269-baseline"], ["Readonly Approval Check", "/api/v270/readonly-approval-check"], ["Readonly Adapter Descriptor Check", "/api/v270/readonly-adapter-descriptor-check"], ["Allowed Calls Check", "/api/v270/allowed-calls-check"], ["Forbidden Calls Check", "/api/v270/forbidden-calls-check"], ["Secret Redaction Check", "/api/v270/secret-redaction-check"], ["Private Data Minimization Check", "/api/v270/private-data-minimization-check"], ["Failure Code", "/api/v270/failure-code"], ["No Submit Cancel Proof", "/api/v270/no-submit-cancel-proof"], ["No Broker Contact Proof", "/api/v270/no-broker-contact-proof"], ["Readiness Governor", "/api/v270/readiness-governor"], ["Execution Lock", "/api/v270/execution-lock"], ["Mission State", "/api/v270/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Broker Readonly Verifier", "broker_readonly_optional_verifier_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V270Dashboard() {
  return <StageDashboard title="Dummy V270 Broker Readonly Optional Verifier No Submit Cancel" endpoints={endpoints} missionKey="dummy_mission_state_report_v256" summaryFields={summaryFields} />;
}
