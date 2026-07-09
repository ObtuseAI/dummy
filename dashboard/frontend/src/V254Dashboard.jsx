import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V5 Controller", "/api/v254/completion-lift-v5-controller"], ["V253 Baseline", "/api/v254/v253-baseline"], ["Proof Aware Percentages", "/api/v254/proof-aware-percentages"], ["Operator Action Map", "/api/v254/operator-action-map"], ["Next Action Matrix", "/api/v254/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v254/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v254/no-submit-proof"], ["No Broker Contact Proof", "/api/v254/no-broker-contact-proof"], ["No Scale Proof", "/api/v254/no-scale-proof"], ["No Autonomy Proof", "/api/v254/no-autonomy-proof"], ["Readiness Governor", "/api/v254/readiness-governor"], ["Execution Lock", "/api/v254/execution-lock"], ["Mission State", "/api/v254/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V5", "completion_lift_v5_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V254Dashboard() {
  return <StageDashboard title="Dummy V254 Completion Lift V5 Operator Ready Lock And Next Phase Map" endpoints={endpoints} missionKey="dummy_mission_state_report_v240" summaryFields={summaryFields} />;
}
