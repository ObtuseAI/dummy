import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Final Proof Runner V7", "/api/v298/execute-once-final-proof-runner-v7"], ["V297 Baseline", "/api/v298/v297-baseline"], ["Arm Requirements", "/api/v298/arm-requirements"], ["No Fixture Inflation Proof", "/api/v298/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v298/no-submit-proof"], ["No Broker Contact Proof", "/api/v298/no-broker-contact-proof"], ["Readiness Governor", "/api/v298/readiness-governor"], ["Execution Lock", "/api/v298/execution-lock"], ["Mission State", "/api/v298/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Runner", "execute_once_final_proof_runner_v7_controller_status"], ["Next Action", "current_next_action"]];

export default function V298Dashboard() {
  return <StageDashboard title="Dummy V298 Execute-Once Final Proof Runner V7" endpoints={endpoints} missionKey="dummy_mission_state_report_v298" summaryFields={summaryFields} />;
}
