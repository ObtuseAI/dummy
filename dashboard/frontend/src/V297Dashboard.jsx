import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Command Seal", "/api/v297/execute-once-command-seal"], ["V296 Baseline", "/api/v297/v296-baseline"], ["Seal Manifest", "/api/v297/seal-manifest"], ["No Submit Proof", "/api/v297/no-submit-proof"], ["No Broker Contact Proof", "/api/v297/no-broker-contact-proof"], ["No Mutation Proof", "/api/v297/no-mutation-proof"], ["Readiness Governor", "/api/v297/readiness-governor"], ["Execution Lock", "/api/v297/execution-lock"], ["Mission State", "/api/v297/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Seal", "execute_once_command_seal_controller_status"], ["State", "seal_state"], ["Next Action", "current_next_action"]];

export default function V297Dashboard() {
  return <StageDashboard title="Dummy V297 Execute-Once Command Seal" endpoints={endpoints} missionKey="dummy_mission_state_report_v297" summaryFields={summaryFields} />;
}
