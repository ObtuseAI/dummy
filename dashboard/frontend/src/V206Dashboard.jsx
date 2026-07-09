import StageDashboard from './StageDashboard';

const endpoints = [["Activation Manifest Controller", "/api/v206/activation-manifest-controller"], ["V205 Baseline", "/api/v206/v205-baseline"], ["Manifest Schema", "/api/v206/manifest-schema"], ["Manifest Linter", "/api/v206/manifest-linter"], ["Production Pilot Approval Lint", "/api/v206/production-pilot-approval-lint"], ["Controlled Session Approval Lint", "/api/v206/controlled-session-approval-lint"], ["Broker Readonly Approval Lint", "/api/v206/broker-readonly-approval-lint"], ["Broad Fuzzy Approval Rejection", "/api/v206/broad-fuzzy-approval-rejection"], ["Hash Only Ledger", "/api/v206/hash-only-ledger"], ["No Raw Phrase Leakage Proof", "/api/v206/no-raw-phrase-leakage-proof"], ["No Approval File Write Proof", "/api/v206/no-approval-file-write-proof"], ["No Submit Proof", "/api/v206/no-submit-proof"], ["Readiness Governor", "/api/v206/readiness-governor"], ["Execution Lock", "/api/v206/execution-lock"], ["Mission State", "/api/v206/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Manifest Linter", "activation_manifest_controller_status"], ["Approval Files Written", "approval_files_written"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V206Dashboard() {
  return <StageDashboard title="Dummy V206 Operator Activation Manifest Linter" endpoints={endpoints} missionKey="dummy_mission_state_report_v192" summaryFields={summaryFields} />;
}
