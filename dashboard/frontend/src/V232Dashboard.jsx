import StageDashboard from './StageDashboard';

const endpoints = [["Route Decision Controller", "/api/v232/route-decision-controller"], ["V231 Baseline", "/api/v232/v231-baseline"], ["Live Proof Prerequisite", "/api/v232/live-proof-prerequisite"], ["Reconcile Forensic Prerequisite", "/api/v232/reconcile-forensic-prerequisite"], ["Repeat Pilot Readiness", "/api/v232/repeat-pilot-readiness"], ["Controlled Session Readiness", "/api/v232/controlled-session-readiness"], ["Scale Review Readiness", "/api/v232/scale-review-readiness"], ["Autonomy Review Readiness", "/api/v232/autonomy-review-readiness"], ["Route State", "/api/v232/route-state"], ["No Submit Proof", "/api/v232/no-submit-proof"], ["No Scale Proof", "/api/v232/no-scale-proof"], ["No Autonomy Proof", "/api/v232/no-autonomy-proof"], ["Readiness Governor", "/api/v232/readiness-governor"], ["Execution Lock", "/api/v232/execution-lock"], ["Mission State", "/api/v232/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Route Decision", "route_decision_controller_status"], ["Route State", "route_state"], ["Next Action", "current_next_action"], ["Scale Applied", "scale_applied"], ["Blockers", "current_blockers"]];

export default function V232Dashboard() {
  return <StageDashboard title="Dummy V232 Proof Aware Route Decision" endpoints={endpoints} missionKey="dummy_mission_state_report_v218" summaryFields={summaryFields} />;
}
