import StageDashboard from './StageDashboard';

const endpoints = [["Scale Evidence Controller", "/api/v171/scale-evidence-controller"], ["V170 Baseline", "/api/v171/v170-baseline"], ["Scale Approval Validator", "/api/v171/scale-approval-validator"], ["First Pilot Evidence Prerequisite", "/api/v171/first-pilot-evidence-prerequisite"], ["Repeat Pilot Evidence Prerequisite", "/api/v171/repeat-pilot-evidence-prerequisite"], ["Pilot Pair Audit Prerequisite", "/api/v171/pilot-pair-audit-prerequisite"], ["Risk Policy Prerequisite", "/api/v171/risk-policy-prerequisite"], ["Abstention Quality Prerequisite", "/api/v171/abstention-quality-prerequisite"], ["Live Submit Caps Unchanged Proof", "/api/v171/live-submit-caps-unchanged-proof"], ["No Loss Lock", "/api/v171/no-loss-lock"], ["No Drift Lock", "/api/v171/no-drift-lock"], ["Scale Recommendation", "/api/v171/scale-recommendation"], ["No Caps Modification Proof", "/api/v171/no-caps-modification-proof"], ["No Order Proof", "/api/v171/no-order-proof"], ["Readiness Governor", "/api/v171/readiness-governor"], ["Execution Lock", "/api/v171/execution-lock"], ["Mission State", "/api/v171/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scale Evidence", "scale_evidence_controller_status"], ["Recommendation", "scale_recommendation"], ["Scale Applied", "scale_applied"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V171Dashboard() {
  return <StageDashboard title="Dummy V171 Scale-Step 1 Evidence Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v157" summaryFields={summaryFields} />;
}
