import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V7 Controller", "/api/v274/completion-lift-v7-controller"], ["V273 Baseline", "/api/v274/v273-baseline"], ["Proof Aware Percentages", "/api/v274/proof-aware-percentages"], ["Operator Action Map", "/api/v274/operator-action-map"], ["Next Action Matrix", "/api/v274/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v274/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v274/no-submit-proof"], ["No Broker Contact Proof", "/api/v274/no-broker-contact-proof"], ["No Scale Proof", "/api/v274/no-scale-proof"], ["No Autonomy Proof", "/api/v274/no-autonomy-proof"], ["Readiness Governor", "/api/v274/readiness-governor"], ["Execution Lock", "/api/v274/execution-lock"], ["Mission State", "/api/v274/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V7", "completion_lift_v7_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V274Dashboard() {
  return <StageDashboard title="Dummy V274 Completion Lift V7 Route Lock And Next Operator Actions" endpoints={endpoints} missionKey="dummy_mission_state_report_v260" summaryFields={summaryFields} />;
}
