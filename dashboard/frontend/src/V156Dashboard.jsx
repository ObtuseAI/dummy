import StageDashboard from './StageDashboard';

const endpoints = [["Approval Linter Controller", "/api/v156/approval-linter-controller"], ["V155 Baseline", "/api/v156/v155-baseline"], ["Production Pilot Approval Linter", "/api/v156/production-pilot-approval-linter"], ["Broker Readonly Approval Linter", "/api/v156/broker-readonly-approval-linter"], ["Repeat Pilot Approval Linter", "/api/v156/repeat-pilot-approval-linter"], ["Scale Approval Linter", "/api/v156/scale-approval-linter"], ["Controlled Operation Approval Linter", "/api/v156/controlled-operation-approval-linter"], ["Broad Fuzzy Approval Rejection", "/api/v156/broad-fuzzy-approval-rejection"], ["Hash Only Ledger", "/api/v156/hash-only-ledger"], ["No Raw Phrase Leakage Proof", "/api/v156/no-raw-phrase-leakage-proof"], ["No Approval File Write Proof", "/api/v156/no-approval-file-write-proof"], ["No Submit Proof", "/api/v156/no-submit-proof"], ["No Broker Contact Proof", "/api/v156/no-broker-contact-proof"], ["Readiness Governor", "/api/v156/readiness-governor"], ["Execution Lock", "/api/v156/execution-lock"], ["Mission State", "/api/v156/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Approval Linter", "approval_linter_controller_status"], ["Approval Files Written", "approval_files_written"], ["Broker Contacted", "broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V156Dashboard() {
  return <StageDashboard title="Dummy V156 Operator Approval-File Linter" endpoints={endpoints} missionKey="dummy_mission_state_report_v142" summaryFields={summaryFields} />;
}
