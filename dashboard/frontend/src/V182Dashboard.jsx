import StageDashboard from './StageDashboard';

const endpoints = [["Autonomy Evidence Controller", "/api/v182/autonomy-evidence-controller"], ["V181 Baseline", "/api/v182/v181-baseline"], ["Autonomy Review Approval Validator", "/api/v182/autonomy-review-approval-validator"], ["Pilot Evidence Prerequisite", "/api/v182/pilot-evidence-prerequisite"], ["Repeat Evidence Prerequisite", "/api/v182/repeat-evidence-prerequisite"], ["Session Evidence Prerequisite", "/api/v182/session-evidence-prerequisite"], ["Risk Governor Prerequisite", "/api/v182/risk-governor-prerequisite"], ["Abstention Governor Prerequisite", "/api/v182/abstention-governor-prerequisite"], ["Scale Status Prerequisite", "/api/v182/scale-status-prerequisite"], ["Controlled Operation Status Prerequisite", "/api/v182/controlled-operation-status-prerequisite"], ["Autonomy Eligibility", "/api/v182/autonomy-eligibility"], ["No Autonomous Order Proof", "/api/v182/no-autonomous-order-proof"], ["No Live Submit Caps Change Proof", "/api/v182/no-live-submit-caps-change-proof"], ["No Scale Proof", "/api/v182/no-scale-proof"], ["Readiness Governor", "/api/v182/readiness-governor"], ["Execution Lock", "/api/v182/execution-lock"], ["Mission State", "/api/v182/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Autonomy Evidence", "autonomy_evidence_controller_status"], ["Eligibility", "autonomy_eligibility"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V182Dashboard() {
  return <StageDashboard title="Dummy V182 Autonomy Evidence Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v168" summaryFields={summaryFields} />;
}
