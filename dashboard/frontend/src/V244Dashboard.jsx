import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift Lock V4 Controller", "/api/v244/completion-lift-lock-v4-controller"], ["V243 Baseline", "/api/v244/v243-baseline"], ["Proof Aware Percentages", "/api/v244/proof-aware-percentages"], ["Operator Action Map", "/api/v244/operator-action-map"], ["Next Action Matrix", "/api/v244/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v244/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v244/no-submit-proof"], ["No Broker Contact Proof", "/api/v244/no-broker-contact-proof"], ["No Scale Proof", "/api/v244/no-scale-proof"], ["No Autonomy Proof", "/api/v244/no-autonomy-proof"], ["Readiness Governor", "/api/v244/readiness-governor"], ["Execution Lock", "/api/v244/execution-lock"], ["Mission State", "/api/v244/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V4", "completion_lift_lock_v4_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V244Dashboard() {
  return <StageDashboard title="Dummy V244 Completion Lift Lock V4 Operator Action Map And Percentage Update" endpoints={endpoints} missionKey="dummy_mission_state_report_v230" summaryFields={summaryFields} />;
}
