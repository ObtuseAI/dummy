import StageDashboard from './StageDashboard';

const endpoints = [["Authority Manifest Doctor Controller", "/api/v236/authority-manifest-doctor-controller"], ["V235 Baseline", "/api/v236/v235-baseline"], ["Expected Approval Paths Check", "/api/v236/expected-approval-paths-check"], ["Exact Phrase Check", "/api/v236/exact-phrase-check"], ["Operator Metadata Check", "/api/v236/operator-metadata-check"], ["Expiration Check", "/api/v236/expiration-check"], ["Proof Target Check", "/api/v236/proof-target-check"], ["Descriptor Check", "/api/v236/descriptor-check"], ["Failure Code", "/api/v236/failure-code"], ["Hash Only Ledger", "/api/v236/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v236/no-raw-phrase-leakage"], ["No Approval File Write Proof", "/api/v236/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v236/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v236/no-submit-proof"], ["Readiness Governor", "/api/v236/readiness-governor"], ["Execution Lock", "/api/v236/execution-lock"], ["Mission State", "/api/v236/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Manifest Doctor", "authority_manifest_doctor_controller_status"], ["Manifest Valid", "manifest_valid"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V236Dashboard() {
  return <StageDashboard title="Dummy V236 Authority Manifest Doctor External Only No Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v222" summaryFields={summaryFields} />;
}
