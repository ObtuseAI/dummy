import StageDashboard from './StageDashboard';

const endpoints = [["Completion Scoreboard Controller", "/api/v213/completion-scoreboard-controller"], ["V212 Baseline", "/api/v213/v212-baseline"], ["Subsystem Percentages", "/api/v213/subsystem-percentages"], ["Remaining Blocker Count", "/api/v213/remaining-blocker-count"], ["Proof Status Count", "/api/v213/proof-status-count"], ["Fully Operational Estimate", "/api/v213/fully-operational-estimate"], ["Exact Next Action", "/api/v213/exact-next-action"], ["No Submit Proof", "/api/v213/no-submit-proof"], ["No Broker Contact Proof", "/api/v213/no-broker-contact-proof"], ["Readiness Governor", "/api/v213/readiness-governor"], ["Execution Lock", "/api/v213/execution-lock"], ["Mission State", "/api/v213/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Scoreboard", "completion_scoreboard_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Remaining Blockers", "remaining_blocker_count"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V213Dashboard() {
  return <StageDashboard title="Dummy V213 Completion Scoreboard" endpoints={endpoints} missionKey="dummy_mission_state_report_v199" summaryFields={summaryFields} />;
}
