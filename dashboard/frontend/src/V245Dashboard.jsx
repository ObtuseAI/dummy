import StageDashboard from './StageDashboard';

const endpoints = [["Operator Ready Appliance Baseline Controller", "/api/v245/operator-ready-appliance-baseline-controller"], ["V244 Baseline", "/api/v245/v244-baseline"], ["V235 To V244 Readback", "/api/v245/v235-to-v244-readback"], ["Appliance State Classification", "/api/v245/appliance-state-classification"], ["No Approval File Write Proof", "/api/v245/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v245/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v245/no-submit-proof"], ["No Broker Contact Proof", "/api/v245/no-broker-contact-proof"], ["Readiness Governor", "/api/v245/readiness-governor"], ["Execution Lock", "/api/v245/execution-lock"], ["Mission State", "/api/v245/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Appliance Baseline", "operator_ready_appliance_baseline_controller_status"], ["Operator Ready State", "operator_ready_state"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V245Dashboard() {
  return <StageDashboard title="Dummy V245 Operator Ready Appliance Baseline From V235 To V244" endpoints={endpoints} missionKey="dummy_mission_state_report_v231" summaryFields={summaryFields} />;
}
