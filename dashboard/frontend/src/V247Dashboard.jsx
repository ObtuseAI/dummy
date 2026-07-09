import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Rehearsal Controller", "/api/v247/external-authority-rehearsal-controller"], ["V246 Baseline", "/api/v247/v246-baseline"], ["Rehearsal Cases", "/api/v247/rehearsal-cases"], ["Hash Only Ledger", "/api/v247/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v247/no-raw-phrase-leakage"], ["No Approval File Write Proof", "/api/v247/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v247/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v247/no-submit-proof"], ["No Broker Contact Proof", "/api/v247/no-broker-contact-proof"], ["Readiness Governor", "/api/v247/readiness-governor"], ["Execution Lock", "/api/v247/execution-lock"], ["Mission State", "/api/v247/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Authority Rehearsal", "external_authority_rehearsal_controller_status"], ["Approval Files Written", "approval_files_written"], ["Runtime Approvals Created", "runtime_approvals_created_by_dummy"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V247Dashboard() {
  return <StageDashboard title="Dummy V247 External Authority Rehearsal Inert No Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v233" summaryFields={summaryFields} />;
}
