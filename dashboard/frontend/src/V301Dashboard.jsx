import StageDashboard from './StageDashboard';

const endpoints = [["Post Proof Route Autopilot", "/api/v301/post-proof-route-autopilot"], ["V300 Baseline", "/api/v301/v300-baseline"], ["Route State", "/api/v301/route-state"], ["No Submit Proof", "/api/v301/no-submit-proof"], ["No Scale Proof", "/api/v301/no-scale-proof"], ["No Autonomy Proof", "/api/v301/no-autonomy-proof"], ["Readiness Governor", "/api/v301/readiness-governor"], ["Execution Lock", "/api/v301/execution-lock"], ["Mission State", "/api/v301/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Route", "post_proof_route_autopilot_controller_status"], ["State", "route_state"], ["Next Action", "current_next_action"]];

export default function V301Dashboard() {
  return <StageDashboard title="Dummy V301 Post-Proof Route Autopilot" endpoints={endpoints} missionKey="dummy_mission_state_report_v301" summaryFields={summaryFields} />;
}
