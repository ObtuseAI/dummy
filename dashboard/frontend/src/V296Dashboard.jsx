import StageDashboard from './StageDashboard';

const endpoints = [["Operator Execution Fork", "/api/v296/operator-execution-fork"], ["V295 Baseline", "/api/v296/v295-baseline"], ["Fork State", "/api/v296/fork-state"], ["No Submit Proof", "/api/v296/no-submit-proof"], ["No Broker Contact Proof", "/api/v296/no-broker-contact-proof"], ["Readiness Governor", "/api/v296/readiness-governor"], ["Execution Lock", "/api/v296/execution-lock"], ["Mission State", "/api/v296/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Fork", "operator_execution_fork_controller_status"], ["State", "fork_state"], ["Next Action", "current_next_action"]];

export default function V296Dashboard() {
  return <StageDashboard title="Dummy V296 Operator Execution Fork" endpoints={endpoints} missionKey="dummy_mission_state_report_v296" summaryFields={summaryFields} />;
}
