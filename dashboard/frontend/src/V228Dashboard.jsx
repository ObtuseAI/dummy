import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Intake V2 Controller", "/api/v228/external-authority-intake-v2-controller"], ["V227 Baseline", "/api/v228/v227-baseline"], ["Exact Approval Files Check", "/api/v228/exact-approval-files-check"], ["Operator Metadata Check", "/api/v228/operator-metadata-check"], ["Expiration Check", "/api/v228/expiration-check"], ["Descriptor Check", "/api/v228/descriptor-check"], ["Proof Target Selector Check", "/api/v228/proof-target-selector-check"], ["Hash Only Ledger", "/api/v228/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v228/no-raw-phrase-leakage"], ["No File Writes Proof", "/api/v228/no-file-writes-proof"], ["No Runtime Approvals Proof", "/api/v228/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v228/no-submit-proof"], ["Readiness Governor", "/api/v228/readiness-governor"], ["Execution Lock", "/api/v228/execution-lock"], ["Mission State", "/api/v228/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Intake V2", "external_authority_intake_v2_controller_status"], ["Intake Valid", "intake_valid"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V228Dashboard() {
  return <StageDashboard title="Dummy V228 External Authority Intake V2 Validate Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v214" summaryFields={summaryFields} />;
}
