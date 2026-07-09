import StageDashboard from './StageDashboard';

const endpoints = [["Scale Review Controller", "/api/v123/scale-review-controller"], ["V122 Baseline", "/api/v123/v122-baseline"], ["Scale Approval Validator", "/api/v123/scale-approval-validator"], ["Pilot Evidence Prerequisite", "/api/v123/pilot-evidence-prerequisite"], ["Risk Prerequisite", "/api/v123/risk-prerequisite"], ["Abstention Prerequisite", "/api/v123/abstention-prerequisite"], ["Production Readiness Prerequisite", "/api/v123/production-readiness-prerequisite"], ["Scale Recommendation", "/api/v123/scale-recommendation"], ["No Caps Modification Proof", "/api/v123/no-caps-modification-proof"], ["No Auto Order Proof", "/api/v123/no-auto-order-proof"], ["Readiness Governor", "/api/v123/readiness-governor"], ["Execution Lock", "/api/v123/execution-lock"], ["Mission State", "/api/v123/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scale Review", "scale_review_controller_status"], ["Recommendation", "scale_recommendation"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V123Dashboard() {
  return <StageDashboard title="Dummy V123 Scale Step 1 Review Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v109" summaryFields={summaryFields} />;
}
