import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Final Run Wrapper V6", "/api/v289/execute-once-final-run-wrapper-v6"], ["V288 Baseline", "/api/v289/v288-baseline"], ["Arm Requirements", "/api/v289/arm-requirements"], ["No Fixture Inflation Proof", "/api/v289/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v289/no-submit-proof"], ["No Broker Contact Proof", "/api/v289/no-broker-contact-proof"], ["Readiness Governor", "/api/v289/readiness-governor"], ["Execution Lock", "/api/v289/execution-lock"], ["Mission State", "/api/v289/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execute-Once", "execute_once_final_run_wrapper_v6_controller_status"], ["Next Action", "current_next_action"]];

export default function V289Dashboard() {
  return <StageDashboard title="Dummy V289 Execute-Once Final Run Wrapper V6" endpoints={endpoints} missionKey="dummy_mission_state_report_v289" summaryFields={summaryFields} />;
}
