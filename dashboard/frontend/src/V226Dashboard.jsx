import StageDashboard from './StageDashboard';

const endpoints = [["Manifest Pack Controller", "/api/v226/manifest-pack-controller"], ["V225 Baseline", "/api/v226/v225-baseline"], ["Manifest Pack Template", "/api/v226/manifest-pack-template"], ["Required Approval Files List", "/api/v226/required-approval-files-list"], ["Required Exact Phrases List", "/api/v226/required-exact-phrases-list"], ["Required Descriptors List", "/api/v226/required-descriptors-list"], ["Manifest Linter", "/api/v226/manifest-linter"], ["No Approval File Write Proof", "/api/v226/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v226/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v226/no-submit-proof"], ["Readiness Governor", "/api/v226/readiness-governor"], ["Execution Lock", "/api/v226/execution-lock"], ["Mission State", "/api/v226/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Manifest Pack", "manifest_pack_controller_status"], ["Approval Files Written", "approval_files_written"], ["Runtime Approvals Created", "runtime_approvals_created_by_dummy"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V226Dashboard() {
  return <StageDashboard title="Dummy V226 Operator Authority Manifest Pack Template Linter Readonly" endpoints={endpoints} missionKey="dummy_mission_state_report_v212" summaryFields={summaryFields} />;
}
