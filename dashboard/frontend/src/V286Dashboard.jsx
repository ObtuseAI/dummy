import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Seal Verifier", "/api/v286/external-authority-seal-verifier"], ["V285 Baseline", "/api/v286/v285-baseline"], ["Seal State", "/api/v286/seal-state"], ["No Approval Writes Proof", "/api/v286/no-approval-writes-proof"], ["No Submit Proof", "/api/v286/no-submit-proof"], ["No Broker Contact Proof", "/api/v286/no-broker-contact-proof"], ["Readiness Governor", "/api/v286/readiness-governor"], ["Execution Lock", "/api/v286/execution-lock"], ["Mission State", "/api/v286/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Seal", "external_authority_seal_verifier_controller_status"], ["State", "seal_state"], ["Next Action", "current_next_action"]];

export default function V286Dashboard() {
  return <StageDashboard title="Dummy V286 External Authority Seal Verifier" endpoints={endpoints} missionKey="dummy_mission_state_report_v286" summaryFields={summaryFields} />;
}
