import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Pilot Post Proof Readiness", "/api/v281/repeat-pilot-post-proof-readiness"], ["V280 Baseline", "/api/v281/v280-baseline"], ["Readiness Checks", "/api/v281/readiness-checks"], ["No Submit Proof", "/api/v281/no-submit-proof"], ["No Scale Proof", "/api/v281/no-scale-proof"], ["No Autonomy Proof", "/api/v281/no-autonomy-proof"], ["Readiness Governor", "/api/v281/readiness-governor"], ["Execution Lock", "/api/v281/execution-lock"], ["Mission State", "/api/v281/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Readiness", "repeat_pilot_post_proof_readiness_controller_status"], ["State", "repeat_state"], ["Next Action", "current_next_action"]];

export default function V281Dashboard() {
  return <StageDashboard title="Dummy V281 Repeat Pilot Post-Proof Readiness" endpoints={endpoints} missionKey="dummy_mission_state_report_v281" summaryFields={summaryFields} />;
}
