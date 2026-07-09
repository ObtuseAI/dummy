import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V10 Controller", "/api/v304/completion-lift-v10-controller"], ["V303 Baseline", "/api/v304/v303-baseline"], ["Proof Aware Percentages", "/api/v304/proof-aware-percentages"], ["Next Action Matrix", "/api/v304/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v304/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v304/no-submit-proof"], ["No Broker Contact Proof", "/api/v304/no-broker-contact-proof"], ["No Scale Proof", "/api/v304/no-scale-proof"], ["No Autonomy Proof", "/api/v304/no-autonomy-proof"], ["Readiness Governor", "/api/v304/readiness-governor"], ["Execution Lock", "/api/v304/execution-lock"], ["Mission State", "/api/v304/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V10", "completion_lift_v10_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"]];

export default function V304Dashboard() {
  return <StageDashboard title="Dummy V304 Completion Lift V10 Real-Proof Fork Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v304" summaryFields={summaryFields} />;
}
