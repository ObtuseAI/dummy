import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V6 Controller", "/api/v264/completion-lift-v6-controller"], ["V263 Baseline", "/api/v264/v263-baseline"], ["Proof Aware Percentages", "/api/v264/proof-aware-percentages"], ["Operator Action Map", "/api/v264/operator-action-map"], ["Next Action Matrix", "/api/v264/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v264/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v264/no-submit-proof"], ["No Broker Contact Proof", "/api/v264/no-broker-contact-proof"], ["No Scale Proof", "/api/v264/no-scale-proof"], ["No Autonomy Proof", "/api/v264/no-autonomy-proof"], ["Readiness Governor", "/api/v264/readiness-governor"], ["Execution Lock", "/api/v264/execution-lock"], ["Mission State", "/api/v264/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V6", "completion_lift_v6_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V264Dashboard() {
  return <StageDashboard title="Dummy V264 Completion Lift V6 First Proof Ready Lock And Next Action Map" endpoints={endpoints} missionKey="dummy_mission_state_report_v250" summaryFields={summaryFields} />;
}
