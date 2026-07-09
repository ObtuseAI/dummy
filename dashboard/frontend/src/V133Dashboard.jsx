import StageDashboard from './StageDashboard';

const endpoints = [["Scale Review Controller", "/api/v133/scale-review-controller"], ["V132 Baseline", "/api/v133/v132-baseline"], ["Scale Approval Validator", "/api/v133/scale-approval-validator"], ["Pilot Evidence Prerequisite", "/api/v133/pilot-evidence-prerequisite"], ["Risk Prerequisite", "/api/v133/risk-prerequisite"], ["Abstention Prerequisite", "/api/v133/abstention-prerequisite"], ["Production Readiness Prerequisite", "/api/v133/production-readiness-prerequisite"], ["Scale Recommendation", "/api/v133/scale-recommendation"], ["No Caps Modification Proof", "/api/v133/no-caps-modification-proof"], ["No Auto Order Proof", "/api/v133/no-auto-order-proof"], ["Readiness Governor", "/api/v133/readiness-governor"], ["Execution Lock", "/api/v133/execution-lock"], ["Mission State", "/api/v133/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scale Review", "scale_review_controller_status"], ["Recommendation", "scale_recommendation"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V133Dashboard() {
  return <StageDashboard title="Dummy V133 Scale Step 1 Review Gate V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v119" summaryFields={summaryFields} />;
}
