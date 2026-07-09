import StageDashboard from './StageDashboard';

const endpoints = [["Completion Lift V8 Controller", "/api/v284/completion-lift-v8-controller"], ["V283 Baseline", "/api/v284/v283-baseline"], ["Proof Aware Percentages", "/api/v284/proof-aware-percentages"], ["Next Action Matrix", "/api/v284/next-action-matrix"], ["No Fixture Inflation Proof", "/api/v284/no-fixture-inflation-proof"], ["No Submit Proof", "/api/v284/no-submit-proof"], ["No Broker Contact Proof", "/api/v284/no-broker-contact-proof"], ["No Scale Proof", "/api/v284/no-scale-proof"], ["No Autonomy Proof", "/api/v284/no-autonomy-proof"], ["Readiness Governor", "/api/v284/readiness-governor"], ["Execution Lock", "/api/v284/execution-lock"], ["Mission State", "/api/v284/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Completion Lift V8", "completion_lift_v8_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"]];

export default function V284Dashboard() {
  return <StageDashboard title="Dummy V284 Completion Lift V8 Final Operator Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v284" summaryFields={summaryFields} />;
}
