import StageDashboard from './StageDashboard';

const endpoints = [["Repeat Authority Binder Controller", "/api/v165/repeat-authority-binder-controller"], ["V164 Baseline", "/api/v165/v164-baseline"], ["Repeat Approval File Validator", "/api/v165/repeat-approval-file-validator"], ["First Pilot Reconcile Proof Checker", "/api/v165/first-pilot-reconcile-proof-checker"], ["First Pilot Forensic Proof Checker", "/api/v165/first-pilot-forensic-proof-checker"], ["Live Submit Caps Status Checker", "/api/v165/live-submit-caps-status-checker"], ["Firewall Adapter Checker", "/api/v165/firewall-adapter-checker"], ["Broker Readonly Checker", "/api/v165/broker-readonly-checker"], ["Approval Hash Only Ledger", "/api/v165/approval-hash-only-ledger"], ["Authority Gap Map", "/api/v165/authority-gap-map"], ["No Submit Proof", "/api/v165/no-submit-proof"], ["No Broker Contact Proof", "/api/v165/no-broker-contact-proof"], ["No Approval File Write Proof", "/api/v165/no-approval-file-write-proof"], ["Readiness Governor", "/api/v165/readiness-governor"], ["Execution Lock", "/api/v165/execution-lock"], ["Mission State", "/api/v165/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Repeat Authority", "repeat_authority_binder_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V165Dashboard() {
  return <StageDashboard title="Dummy V165 Repeat Pilot Authority Binder" endpoints={endpoints} missionKey="dummy_mission_state_report_v151" summaryFields={summaryFields} />;
}
