import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Import Wizard Controller", "/api/v266/external-authority-import-wizard-controller"], ["V265 Baseline", "/api/v266/v265-baseline"], ["Import Input Validation", "/api/v266/import-input-validation"], ["Descriptor Checks", "/api/v266/descriptor-checks"], ["Failure Code", "/api/v266/failure-code"], ["Hash Only Ledger", "/api/v266/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v266/no-raw-phrase-leakage"], ["No Approval File Write Proof", "/api/v266/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v266/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v266/no-submit-proof"], ["Readiness Governor", "/api/v266/readiness-governor"], ["Execution Lock", "/api/v266/execution-lock"], ["Mission State", "/api/v266/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Import Wizard", "external_authority_import_wizard_controller_status"], ["Wizard Valid", "wizard_valid"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V266Dashboard() {
  return <StageDashboard title="Dummy V266 External Authority Import Wizard Validate Only No Write" endpoints={endpoints} missionKey="dummy_mission_state_report_v252" summaryFields={summaryFields} />;
}
