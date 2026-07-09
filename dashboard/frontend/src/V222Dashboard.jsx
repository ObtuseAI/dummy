import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Controlled Session Bridge V2 Controller", "/api/v222/repeat-controlled-session-bridge-v2-controller"], ["V221 Baseline", "/api/v222/v221-baseline"], ["Live Proof Prerequisite", "/api/v222/live-proof-prerequisite"], ["Reconcile Prerequisite", "/api/v222/reconcile-prerequisite"], ["Forensic Prerequisite", "/api/v222/forensic-prerequisite"], ["Repeat Pilot Readiness", "/api/v222/repeat-pilot-readiness"], ["Controlled Session Readiness", "/api/v222/controlled-session-readiness"], ["Scale Review Readiness", "/api/v222/scale-review-readiness"], ["Autonomy Review Readiness", "/api/v222/autonomy-review-readiness"], ["Route State", "/api/v222/route-state"], ["No Submit Proof", "/api/v222/no-submit-proof"], ["No Scale Proof", "/api/v222/no-scale-proof"], ["No Autonomy Proof", "/api/v222/no-autonomy-proof"], ["Readiness Governor", "/api/v222/readiness-governor"], ["Execution Lock", "/api/v222/execution-lock"], ["Mission State", "/api/v222/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Bridge", "repeat_controlled_session_bridge_v2_controller_status"], ["Route State", "route_state"], ["Next Action", "current_next_action"], ["Scale Applied", "scale_applied"], ["Blockers", "current_blockers"]];

export default function V222Dashboard() {
  return <StageDashboard title="Dummy V222 Repeat Controlled Session Readiness Bridge V2 After Proof" endpoints={endpoints} missionKey="dummy_mission_state_report_v208" summaryFields={summaryFields} />;
}
