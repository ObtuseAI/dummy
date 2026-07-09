import StageDashboard from './StageDashboard';

const endpoints = [["Final Armability Runbook Controller", "/api/v271/final-armability-runbook-controller"], ["V270 Baseline", "/api/v271/v270-baseline"], ["Import Wizard Summary", "/api/v271/import-wizard-summary"], ["Schema Verifier Summary", "/api/v271/schema-verifier-summary"], ["Caps State Summary", "/api/v271/caps-state-summary"], ["Adapter Appliance Summary", "/api/v271/adapter-appliance-summary"], ["Broker Readonly Summary", "/api/v271/broker-readonly-summary"], ["Resolver State", "/api/v271/resolver-state"], ["Env Gate Status", "/api/v271/env-gate-status"], ["Proof Lock Status", "/api/v271/proof-lock-status"], ["Armability State", "/api/v271/armability-state"], ["No Submit Proof", "/api/v271/no-submit-proof"], ["No Broker Contact Proof", "/api/v271/no-broker-contact-proof"], ["Readiness Governor", "/api/v271/readiness-governor"], ["Execution Lock", "/api/v271/execution-lock"], ["Mission State", "/api/v271/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Armability Runbook", "final_armability_runbook_controller_status"], ["Resolver State", "resolver_state"], ["Armability State", "armability_state"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V271Dashboard() {
  return <StageDashboard title="Dummy V271 Final Armability Runbook Resolver Freeze And Env Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v257" summaryFields={summaryFields} />;
}
