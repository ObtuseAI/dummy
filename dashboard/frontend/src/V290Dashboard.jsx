import StageDashboard from './StageDashboard';

const endpoints = [["Post Proof Autopilot Intake", "/api/v290/post-proof-autopilot-intake"], ["V289 Baseline", "/api/v290/v289-baseline"], ["Attempt Classification", "/api/v290/attempt-classification"], ["No New Order Proof", "/api/v290/no-new-order-proof"], ["No Private Data Leak Proof", "/api/v290/no-private-data-leak-proof"], ["No Broker Contact Proof", "/api/v290/no-broker-contact-proof"], ["Readiness Governor", "/api/v290/readiness-governor"], ["Execution Lock", "/api/v290/execution-lock"], ["Mission State", "/api/v290/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Intake", "post_proof_autopilot_intake_controller_status"], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]];

export default function V290Dashboard() {
  return <StageDashboard title="Dummy V290 Post-Proof Autopilot Intake" endpoints={endpoints} missionKey="dummy_mission_state_report_v290" summaryFields={summaryFields} />;
}
