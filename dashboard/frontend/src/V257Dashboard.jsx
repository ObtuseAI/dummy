import StageDashboard from './StageDashboard';

const endpoints = [["Authority Manifest Validator Controller", "/api/v257/authority-manifest-validator-controller"], ["V256 Baseline", "/api/v257/v256-baseline"], ["Validation Checks", "/api/v257/validation-checks"], ["Fix Hints", "/api/v257/fix-hints"], ["Failure Code", "/api/v257/failure-code"], ["Hash Only Ledger", "/api/v257/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v257/no-raw-phrase-leakage"], ["No Approval File Write Proof", "/api/v257/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v257/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v257/no-submit-proof"], ["Readiness Governor", "/api/v257/readiness-governor"], ["Execution Lock", "/api/v257/execution-lock"], ["Mission State", "/api/v257/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Manifest Validator V3", "authority_manifest_validator_controller_status"], ["Manifest Valid", "manifest_valid"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V257Dashboard() {
  return <StageDashboard title="Dummy V257 Authority Manifest Validator V3 Fix Hints No Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v243" summaryFields={summaryFields} />;
}
