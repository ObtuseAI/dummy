import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Session Fast Route Prep", "/api/v292/repeat-session-fast-route-prep"], ["V291 Baseline", "/api/v292/v291-baseline"], ["Fast Route Checks", "/api/v292/fast-route-checks"], ["No Submit Proof", "/api/v292/no-submit-proof"], ["No Scale Proof", "/api/v292/no-scale-proof"], ["No Autonomy Proof", "/api/v292/no-autonomy-proof"], ["Readiness Governor", "/api/v292/readiness-governor"], ["Execution Lock", "/api/v292/execution-lock"], ["Mission State", "/api/v292/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Fast Route", "repeat_session_fast_route_prep_controller_status"], ["State", "fast_route_state"], ["Next Action", "current_next_action"]];

export default function V292Dashboard() {
  return <StageDashboard title="Dummy V292 Repeat Session Fast-Route Prep" endpoints={endpoints} missionKey="dummy_mission_state_report_v292" summaryFields={summaryFields} />;
}
