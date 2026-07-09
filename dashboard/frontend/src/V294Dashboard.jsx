import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V9 Controller", "/api/v294/completion-lift-v9-controller"], ["V293 Baseline", "/api/v294/v293-baseline"], ["Proof Aware Percentages", "/api/v294/proof-aware-percentages"], ["Next Action Matrix", "/api/v294/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v294/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v294/no-submit-proof"], ["No Broker Contact Proof", "/api/v294/no-broker-contact-proof"], ["No Scale Proof", "/api/v294/no-scale-proof"], ["No Autonomy Proof", "/api/v294/no-autonomy-proof"], ["Readiness Governor", "/api/v294/readiness-governor"], ["Execution Lock", "/api/v294/execution-lock"], ["Mission State", "/api/v294/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V9", "completion_lift_v9_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"]];

export default function V294Dashboard() {
  return <StageDashboard title="Dummy V294 Completion Lift V9 Final Proof-Ready Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v294" summaryFields={summaryFields} />;
}
