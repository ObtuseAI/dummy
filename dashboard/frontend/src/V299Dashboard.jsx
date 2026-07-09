import StageDashboard from './StageDashboard';

const endpoints = [["Post Proof Auto Intake V4", "/api/v299/post-proof-auto-intake-v4"], ["V298 Baseline", "/api/v299/v298-baseline"], ["Attempt Classification", "/api/v299/attempt-classification"], ["No New Order Proof", "/api/v299/no-new-order-proof"], ["No Private Data Leak Proof", "/api/v299/no-private-data-leak-proof"], ["No Broker Contact Proof", "/api/v299/no-broker-contact-proof"], ["Readiness Governor", "/api/v299/readiness-governor"], ["Execution Lock", "/api/v299/execution-lock"], ["Mission State", "/api/v299/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Intake", "post_proof_auto_intake_v4_controller_status"], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]];

export default function V299Dashboard() {
  return <StageDashboard title="Dummy V299 Post-Proof Auto Intake V4" endpoints={endpoints} missionKey="dummy_mission_state_report_v299" summaryFields={summaryFields} />;
}
