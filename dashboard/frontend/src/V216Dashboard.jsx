import StageDashboard from './StageDashboard';

const endpoints = [["External Authority Manifest Intake Controller", "/api/v216/external-authority-manifest-intake-controller"], ["V215 Baseline", "/api/v216/v215-baseline"], ["Exact Approval Files Check", "/api/v216/exact-approval-files-check"], ["Operator Metadata Check", "/api/v216/operator-metadata-check"], ["Timestamps Check", "/api/v216/timestamps-check"], ["Reason Fields Check", "/api/v216/reason-fields-check"], ["Live Submit Descriptor Check", "/api/v216/live-submit-descriptor-check"], ["Caps Descriptor Check", "/api/v216/caps-descriptor-check"], ["Firewall Adapter Descriptor Check", "/api/v216/firewall-adapter-descriptor-check"], ["Proof Target Selector Check", "/api/v216/proof-target-selector-check"], ["Hash Only Ledger", "/api/v216/hash-only-ledger"], ["No Raw Phrase Leakage", "/api/v216/no-raw-phrase-leakage"], ["No File Writes Proof", "/api/v216/no-file-writes-proof"], ["No Submit Proof", "/api/v216/no-submit-proof"], ["Readiness Governor", "/api/v216/readiness-governor"], ["Execution Lock", "/api/v216/execution-lock"], ["Mission State", "/api/v216/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Manifest Intake", "external_authority_manifest_intake_controller_status"], ["Manifest Valid", "manifest_valid"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V216Dashboard() {
  return <StageDashboard title="Dummy V216 External Authority Manifest Intake Validate Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v202" summaryFields={summaryFields} />;
}
