import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Authority Rehearsal V2", "/api/v278/execute-once-authority-rehearsal-v2"], ["V277 Baseline", "/api/v278/v277-baseline"], ["Rehearsal Cases", "/api/v278/rehearsal-cases"], ["Full Authority Fixture", "/api/v278/full-authority-fixture"], ["No Fixture Inflation Proof", "/api/v278/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v278/no-submit-proof"], ["No Broker Contact Proof", "/api/v278/no-broker-contact-proof"], ["Readiness Governor", "/api/v278/readiness-governor"], ["Execution Lock", "/api/v278/execution-lock"], ["Mission State", "/api/v278/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Rehearsal", "execute_once_authority_rehearsal_v2_controller_status"], ["Next Action", "current_next_action"]];

export default function V278Dashboard() {
  return <StageDashboard title="Dummy V278 Execute-Once Authority Rehearsal V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v278" summaryFields={summaryFields} />;
}
