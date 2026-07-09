import StageDashboard from './StageDashboard';

const endpoints = [["Operator Ready Appliance Pack Controller", "/api/v246/operator-ready-appliance-pack-controller"], ["V245 Baseline", "/api/v246/v245-baseline"], ["Appliance Pack", "/api/v246/appliance-pack"], ["Approval File Paths", "/api/v246/approval-file-paths"], ["Command Sequence", "/api/v246/command-sequence"], ["Not Approval Markers", "/api/v246/not-approval-markers"], ["No Approval File Write Proof", "/api/v246/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v246/no-runtime-approvals-proof"], ["No Config Caps Write Proof", "/api/v246/no-config-caps-write-proof"], ["No Submit Proof", "/api/v246/no-submit-proof"], ["Readiness Governor", "/api/v246/readiness-governor"], ["Execution Lock", "/api/v246/execution-lock"], ["Mission State", "/api/v246/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Appliance Pack", "operator_ready_appliance_pack_controller_status"], ["Approval Files Written", "approval_files_written"], ["Runtime Approvals Created", "runtime_approvals_created_by_dummy"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V246Dashboard() {
  return <StageDashboard title="Dummy V246 Operator Ready Appliance Pack Readonly No Approval Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v232" summaryFields={summaryFields} />;
}
