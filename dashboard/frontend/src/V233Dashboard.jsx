import StageDashboard from './StageDashboard';

const endpoints = [["Completion Scoreboard V3 Controller", "/api/v233/completion-scoreboard-v3-controller"], ["V232 Baseline", "/api/v233/v232-baseline"], ["Proof Aware Percentages", "/api/v233/proof-aware-percentages"], ["Live Proof Dependent Uplift", "/api/v233/live-proof-dependent-uplift"], ["Operator Action Blockers", "/api/v233/operator-action-blockers"], ["Next Command Recommendation", "/api/v233/next-command-recommendation"], ["No Submit Proof", "/api/v233/no-submit-proof"], ["No Broker Contact Proof", "/api/v233/no-broker-contact-proof"], ["Readiness Governor", "/api/v233/readiness-governor"], ["Execution Lock", "/api/v233/execution-lock"], ["Mission State", "/api/v233/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scoreboard V3", "completion_scoreboard_v3_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["First Live Proof", "first_live_proof_present"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V233Dashboard() {
  return <StageDashboard title="Dummy V233 Completion Scoreboard V3 Proof Aware Percentages" endpoints={endpoints} missionKey="dummy_mission_state_report_v219" summaryFields={summaryFields} />;
}
