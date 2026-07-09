import StageDashboard from './StageDashboard';

const endpoints = [["Scale Review Controller", "/api/v181/scale-review-controller"], ["V180 Baseline", "/api/v181/v180-baseline"], ["Scale Approval Validator", "/api/v181/scale-approval-validator"], ["First Pilot Evidence Prerequisite", "/api/v181/first-pilot-evidence-prerequisite"], ["Repeat Pilot Evidence Prerequisite", "/api/v181/repeat-pilot-evidence-prerequisite"], ["Controlled Session Evidence Prerequisite", "/api/v181/controlled-session-evidence-prerequisite"], ["Session Decision Prerequisite", "/api/v181/session-decision-prerequisite"], ["Risk Prerequisite", "/api/v181/risk-prerequisite"], ["Abstention Prerequisite", "/api/v181/abstention-prerequisite"], ["Live Submit Caps Unchanged Proof", "/api/v181/live-submit-caps-unchanged-proof"], ["Scale Recommendation", "/api/v181/scale-recommendation"], ["No Caps Modification Proof", "/api/v181/no-caps-modification-proof"], ["No Order Proof", "/api/v181/no-order-proof"], ["Readiness Governor", "/api/v181/readiness-governor"], ["Execution Lock", "/api/v181/execution-lock"], ["Mission State", "/api/v181/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scale Review", "scale_review_controller_status"], ["Recommendation", "scale_recommendation"], ["Scale Applied", "scale_applied"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V181Dashboard() {
  return <StageDashboard title="Dummy V181 Scale Review V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v167" summaryFields={summaryFields} />;
}
