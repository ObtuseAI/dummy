import StageDashboard from './StageDashboard';

const endpoints = [["Operator Execution Appliance Baseline Controller", "/api/v255/operator-execution-appliance-baseline-controller"], ["V254 Baseline", "/api/v255/v254-baseline"], ["V245 To V254 Readback", "/api/v255/v245-to-v254-readback"], ["Appliance State Classification", "/api/v255/appliance-state-classification"], ["No Approval File Write Proof", "/api/v255/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v255/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v255/no-submit-proof"], ["No Broker Contact Proof", "/api/v255/no-broker-contact-proof"], ["Readiness Governor", "/api/v255/readiness-governor"], ["Execution Lock", "/api/v255/execution-lock"], ["Mission State", "/api/v255/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execution Baseline", "operator_execution_appliance_baseline_controller_status"], ["Appliance State", "appliance_state"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V255Dashboard() {
  return <StageDashboard title="Dummy V255 Operator Execution Appliance Baseline From V245 To V254" endpoints={endpoints} missionKey="dummy_mission_state_report_v241" summaryFields={summaryFields} />;
}
