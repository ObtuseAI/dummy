import StageDashboard from './StageDashboard';

const endpoints = [["Handoff Controller", "/api/v146/handoff-controller"], ["V145 Baseline", "/api/v146/v145-baseline"], ["Required Files Checklist", "/api/v146/required-files-checklist"], ["Exact Phrase Checklist", "/api/v146/exact-phrase-checklist"], ["Live Submit Config Checklist", "/api/v146/live-submit-config-checklist"], ["Caps Checklist", "/api/v146/caps-checklist"], ["Firewall Adapter Checklist", "/api/v146/firewall-adapter-checklist"], ["Broker Readonly Approval Checklist", "/api/v146/broker-readonly-approval-checklist"], ["Dry Vs Live Mode Explanation", "/api/v146/dry-vs-live-mode-explanation"], ["No Approval File Write Proof", "/api/v146/no-approval-file-write-proof"], ["No Submit Proof", "/api/v146/no-submit-proof"], ["No Broker Contact Proof", "/api/v146/no-broker-contact-proof"], ["Readiness Governor", "/api/v146/readiness-governor"], ["Execution Lock", "/api/v146/execution-lock"], ["Mission State", "/api/v146/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Handoff", "handoff_controller_status"], ["Approval Files Written", "approval_files_written"], ["Broker Contacted", "broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V146Dashboard() {
  return <StageDashboard title="Dummy V146 Operator Handoff Packet V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v132" summaryFields={summaryFields} />;
}
