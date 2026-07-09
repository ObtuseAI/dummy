import StageDashboard from './StageDashboard';

const endpoints = [["Activation Pipeline Baseline Controller", "/api/v225/activation-pipeline-baseline-controller"], ["V224 Baseline", "/api/v225/v224-baseline"], ["V215 To V224 Readback", "/api/v225/v215-to-v224-readback"], ["Consolidated Accelerator Map", "/api/v225/consolidated-accelerator-map"], ["No Approval File Write Proof", "/api/v225/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v225/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v225/no-submit-proof"], ["No Broker Contact Proof", "/api/v225/no-broker-contact-proof"], ["Readiness Governor", "/api/v225/readiness-governor"], ["Execution Lock", "/api/v225/execution-lock"], ["Mission State", "/api/v225/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Pipeline Baseline", "activation_pipeline_baseline_controller_status"], ["Approval Files Written", "approval_files_written"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V225Dashboard() {
  return <StageDashboard title="Dummy V225 Activation Pipeline Baseline From V215 To V224" endpoints={endpoints} missionKey="dummy_mission_state_report_v211" summaryFields={summaryFields} />;
}
