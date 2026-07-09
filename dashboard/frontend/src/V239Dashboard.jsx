import StageDashboard from './StageDashboard';

const endpoints = [["Broker Readonly Doctor Controller", "/api/v239/broker-readonly-doctor-controller"], ["V238 Baseline", "/api/v239/v238-baseline"], ["Broker Readonly Approval Check", "/api/v239/broker-readonly-approval-check"], ["Readonly Adapter Capability Check", "/api/v239/readonly-adapter-capability-check"], ["Allowed Calls List", "/api/v239/allowed-calls-list"], ["Forbidden Calls List", "/api/v239/forbidden-calls-list"], ["No Submit No Cancel Check", "/api/v239/no-submit-no-cancel-check"], ["Secret Redaction Check", "/api/v239/secret-redaction-check"], ["Private Data Minimization Check", "/api/v239/private-data-minimization-check"], ["Failure Code", "/api/v239/failure-code"], ["No Broker Contact Proof", "/api/v239/no-broker-contact-proof"], ["No Submit Proof", "/api/v239/no-submit-proof"], ["Readiness Governor", "/api/v239/readiness-governor"], ["Execution Lock", "/api/v239/execution-lock"], ["Mission State", "/api/v239/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Broker RO Doctor", "broker_readonly_doctor_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V239Dashboard() {
  return <StageDashboard title="Dummy V239 Broker Readonly Doctor No Submit Cancel" endpoints={endpoints} missionKey="dummy_mission_state_report_v225" summaryFields={summaryFields} />;
}
