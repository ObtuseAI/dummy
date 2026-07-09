import StageDashboard from './StageDashboard';

const endpoints = [["Evidence Refresh Controller", "/api/v202/evidence-refresh-controller"], ["V201 Baseline", "/api/v202/v201-baseline"], ["Scale Approval Validator", "/api/v202/scale-approval-validator"], ["Autonomy Review Approval Validator", "/api/v202/autonomy-review-approval-validator"], ["Live Proof Prerequisite", "/api/v202/live-proof-prerequisite"], ["Forensic Prerequisite", "/api/v202/forensic-prerequisite"], ["Risk Prerequisite", "/api/v202/risk-prerequisite"], ["Abstention Prerequisite", "/api/v202/abstention-prerequisite"], ["Shadow Forensic Prerequisite", "/api/v202/shadow-forensic-prerequisite"], ["Scale Recommendation", "/api/v202/scale-recommendation"], ["Autonomy Recommendation", "/api/v202/autonomy-recommendation"], ["No Caps Modification Proof", "/api/v202/no-caps-modification-proof"], ["No Autonomous Order Proof", "/api/v202/no-autonomous-order-proof"], ["No Submit Proof", "/api/v202/no-submit-proof"], ["Readiness Governor", "/api/v202/readiness-governor"], ["Execution Lock", "/api/v202/execution-lock"], ["Mission State", "/api/v202/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Evidence Refresh", "evidence_refresh_controller_status"], ["Scale", "scale_recommendation"], ["Autonomy", "autonomy_recommendation"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V202Dashboard() {
  return <StageDashboard title="Dummy V202 Scale & Autonomy Evidence Refresh" endpoints={endpoints} missionKey="dummy_mission_state_report_v188" summaryFields={summaryFields} />;
}
