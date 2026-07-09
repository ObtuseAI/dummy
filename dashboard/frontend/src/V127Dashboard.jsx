import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Tieout Controller", "/api/v127/pilot-tieout-controller"], ["V126 Baseline", "/api/v127/v126-baseline"], ["Pilot Approval Validator", "/api/v127/pilot-approval-validator"], ["Live Submit Readonly Checker", "/api/v127/live-submit-readonly-checker"], ["Caps Readonly Checker", "/api/v127/caps-readonly-checker"], ["Firewall Adapter Presence Checker", "/api/v127/firewall-adapter-presence-checker"], ["No Direct Broker Bypass Proof", "/api/v127/no-direct-broker-bypass-proof"], ["No Broker Contact Proof", "/api/v127/no-broker-contact-proof"], ["No Account Private Data Proof", "/api/v127/no-account-private-data-proof"], ["Kill Switch Prerequisite", "/api/v127/kill-switch-prerequisite"], ["Rollback Prerequisite", "/api/v127/rollback-prerequisite"], ["Idempotency Prerequisite", "/api/v127/idempotency-prerequisite"], ["No Submit Proof", "/api/v127/no-submit-proof"], ["Readiness Governor", "/api/v127/readiness-governor"], ["Execution Lock", "/api/v127/execution-lock"], ["Mission State", "/api/v127/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Tieout", "pilot_tieout_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V127Dashboard() {
  return <StageDashboard title="Dummy V127 Production Pilot Approval/Config Tieout" endpoints={endpoints} missionKey="dummy_mission_state_report_v113" summaryFields={summaryFields} />;
}
