import StageDashboard from './StageDashboard';

const endpoints = [["Operator Authority Appliance Baseline Controller", "/api/v235/operator-authority-appliance-baseline-controller"], ["V234 Baseline", "/api/v235/v234-baseline"], ["V225 To V234 Readback", "/api/v235/v225-to-v234-readback"], ["Appliance Blocker Classification", "/api/v235/appliance-blocker-classification"], ["No Approval File Write Proof", "/api/v235/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v235/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v235/no-submit-proof"], ["No Broker Contact Proof", "/api/v235/no-broker-contact-proof"], ["Readiness Governor", "/api/v235/readiness-governor"], ["Execution Lock", "/api/v235/execution-lock"], ["Mission State", "/api/v235/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Appliance Baseline", "operator_authority_appliance_baseline_controller_status"], ["Approval Files Written", "approval_files_written"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V235Dashboard() {
  return <StageDashboard title="Dummy V235 Operator Authority Appliance Baseline From V225 To V234" endpoints={endpoints} missionKey="dummy_mission_state_report_v221" summaryFields={summaryFields} />;
}
