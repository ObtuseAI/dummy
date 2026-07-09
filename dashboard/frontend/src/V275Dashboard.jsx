import StageDashboard from './StageDashboard';

const endpoints = [["Final Operator Execution Baseline", "/api/v275/final-operator-execution-baseline"], ["V274 Baseline", "/api/v275/v274-baseline"], ["Appliance State Classification", "/api/v275/appliance-state-classification"], ["Canonical Next Action List", "/api/v275/canonical-next-action-list"], ["No Submit Proof", "/api/v275/no-submit-proof"], ["No Broker Contact Proof", "/api/v275/no-broker-contact-proof"], ["Readiness Governor", "/api/v275/readiness-governor"], ["Execution Lock", "/api/v275/execution-lock"], ["Mission State", "/api/v275/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Baseline", "final_operator_execution_baseline_controller_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V275Dashboard() {
  return <StageDashboard title="Dummy V275 Final Operator Execution Baseline" endpoints={endpoints} missionKey="dummy_mission_state_report_v275" summaryFields={summaryFields} />;
}
