import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Session Bundle Prep", "/api/v302/repeat-session-bundle-prep"], ["V301 Baseline", "/api/v302/v301-baseline"], ["Bundle Prep Inputs", "/api/v302/bundle-prep-inputs"], ["No Submit Proof", "/api/v302/no-submit-proof"], ["No Scale Proof", "/api/v302/no-scale-proof"], ["No Autonomy Proof", "/api/v302/no-autonomy-proof"], ["Readiness Governor", "/api/v302/readiness-governor"], ["Execution Lock", "/api/v302/execution-lock"], ["Mission State", "/api/v302/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Bundle Prep", "repeat_session_bundle_prep_controller_status"], ["State", "bundle_prep_state"], ["Next Action", "current_next_action"]];

export default function V302Dashboard() {
  return <StageDashboard title="Dummy V302 Repeat Session Bundle Prep" endpoints={endpoints} missionKey="dummy_mission_state_report_v302" summaryFields={summaryFields} />;
}
