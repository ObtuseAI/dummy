import StageDashboard from './StageDashboard';

const endpoints = [["Completion Scoreboard V2 Controller", "/api/v223/completion-scoreboard-v2-controller"], ["V222 Baseline", "/api/v223/v222-baseline"], ["Proof Aware Percentages", "/api/v223/proof-aware-percentages"], ["Live Proof Dependent Uplift", "/api/v223/live-proof-dependent-uplift"], ["Operator Action Blockers", "/api/v223/operator-action-blockers"], ["Next Command Recommendation", "/api/v223/next-command-recommendation"], ["No Submit Proof", "/api/v223/no-submit-proof"], ["No Broker Contact Proof", "/api/v223/no-broker-contact-proof"], ["Readiness Governor", "/api/v223/readiness-governor"], ["Execution Lock", "/api/v223/execution-lock"], ["Mission State", "/api/v223/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scoreboard V2", "completion_scoreboard_v2_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["First Live Proof", "first_live_proof_present"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V223Dashboard() {
  return <StageDashboard title="Dummy V223 Completion Scoreboard V2 Proof Aware Percentages" endpoints={endpoints} missionKey="dummy_mission_state_report_v209" summaryFields={summaryFields} />;
}
