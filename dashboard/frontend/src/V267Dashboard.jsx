import StageDashboard from './StageDashboard';

const endpoints = [["Approval Manifest Schema Verifier Controller", "/api/v267/approval-manifest-schema-verifier-controller"], ["V266 Baseline", "/api/v267/v266-baseline"], ["Schema Checks", "/api/v267/schema-checks"], ["Fix Hints", "/api/v267/fix-hints"], ["Schema State", "/api/v267/schema-state"], ["Missing Keys", "/api/v267/missing-keys"], ["No Raw Phrase Leakage", "/api/v267/no-raw-phrase-leakage"], ["No Approval File Write Proof", "/api/v267/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v267/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v267/no-submit-proof"], ["Readiness Governor", "/api/v267/readiness-governor"], ["Execution Lock", "/api/v267/execution-lock"], ["Mission State", "/api/v267/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Schema Verifier", "approval_manifest_schema_verifier_controller_status"], ["Schema State", "schema_state"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V267Dashboard() {
  return <StageDashboard title="Dummy V267 Approval Manifest Schema Verifier Strict Fix Hints No Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v253" summaryFields={summaryFields} />;
}
