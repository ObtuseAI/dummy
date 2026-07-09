import StageDashboard from './StageDashboard';

const endpoints = [["Controlled Session Post Proof Readiness", "/api/v282/controlled-session-post-proof-readiness"], ["V281 Baseline", "/api/v282/v281-baseline"], ["Readiness Checks", "/api/v282/readiness-checks"], ["No Submit Proof", "/api/v282/no-submit-proof"], ["No Scale Proof", "/api/v282/no-scale-proof"], ["No Autonomy Proof", "/api/v282/no-autonomy-proof"], ["Readiness Governor", "/api/v282/readiness-governor"], ["Execution Lock", "/api/v282/execution-lock"], ["Mission State", "/api/v282/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Readiness", "controlled_session_post_proof_readiness_controller_status"], ["State", "session_state"], ["Next Action", "current_next_action"]];

export default function V282Dashboard() {
  return <StageDashboard title="Dummy V282 Controlled Session Post-Proof Readiness" endpoints={endpoints} missionKey="dummy_mission_state_report_v282" summaryFields={summaryFields} />;
}
