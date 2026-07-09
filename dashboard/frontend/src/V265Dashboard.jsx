import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Import Baseline Controller", "/api/v265/external-authority-import-baseline-controller"], ["V264 Baseline", "/api/v265/v264-baseline"], ["V255 To V264 Readback", "/api/v265/v255-to-v264-readback"], ["Appliance State Classification", "/api/v265/appliance-state-classification"], ["Canonical Next Action List", "/api/v265/canonical-next-action-list"], ["No Approval File Write Proof", "/api/v265/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v265/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v265/no-submit-proof"], ["No Broker Contact Proof", "/api/v265/no-broker-contact-proof"], ["Readiness Governor", "/api/v265/readiness-governor"], ["Execution Lock", "/api/v265/execution-lock"], ["Mission State", "/api/v265/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Import Baseline", "external_authority_import_baseline_controller_status"], ["Appliance State", "appliance_state"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V265Dashboard() {
  return <StageDashboard title="Dummy V265 External Authority Import Baseline From V255 To V264" endpoints={endpoints} missionKey="dummy_mission_state_report_v251" summaryFields={summaryFields} />;
}
