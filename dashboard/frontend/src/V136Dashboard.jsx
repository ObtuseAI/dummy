import StageDashboard from './StageDashboard';

const endpoints = [["Authority Binder Controller", "/api/v136/authority-binder-controller"], ["V135 Baseline", "/api/v136/v135-baseline"], ["Pilot Approval File Validator", "/api/v136/pilot-approval-file-validator"], ["Live Submit Config Reader", "/api/v136/live-submit-config-reader"], ["Caps Config Reader", "/api/v136/caps-config-reader"], ["Firewall Adapter Presence Checker", "/api/v136/firewall-adapter-presence-checker"], ["Broker Readonly Approval Checker", "/api/v136/broker-readonly-approval-checker"], ["Authority Gap Ledger", "/api/v136/authority-gap-ledger"], ["No Submit Proof", "/api/v136/no-submit-proof"], ["No Broker Contact Proof", "/api/v136/no-broker-contact-proof"], ["Readiness Governor", "/api/v136/readiness-governor"], ["Execution Lock", "/api/v136/execution-lock"], ["Mission State", "/api/v136/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Authority Binder", "authority_binder_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V136Dashboard() {
  return <StageDashboard title="Dummy V136 Production Pilot Authority Binder" endpoints={endpoints} missionKey="dummy_mission_state_report_v122" summaryFields={summaryFields} />;
}
