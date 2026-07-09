import StageDashboard from './StageDashboard';

const endpoints = [["First Proof Command Center Controller", "/api/v250/first-proof-command-center-controller"], ["V249 Baseline", "/api/v250/v249-baseline"], ["Current Blocker List", "/api/v250/current-blocker-list"], ["Doctor Status", "/api/v250/doctor-status"], ["Rehearsal Status", "/api/v250/rehearsal-status"], ["Execute Once Command", "/api/v250/execute-once-command"], ["Completion Percentage", "/api/v250/completion-percentage"], ["Ui Readonly Proof", "/api/v250/ui-readonly-proof"], ["No Submit Proof", "/api/v250/no-submit-proof"], ["Readiness Governor", "/api/v250/readiness-governor"], ["Execution Lock", "/api/v250/execution-lock"], ["Mission State", "/api/v250/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Command Center", "first_proof_command_center_controller_status"], ["UI Submit Enabled", "ui_submit_enabled"], ["UI Writes Enabled", "ui_writes_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V250Dashboard() {
  return <StageDashboard title="Dummy V250 First Proof Command Center Readonly Operator Sequence" endpoints={endpoints} missionKey="dummy_mission_state_report_v236" summaryFields={summaryFields} />;
}
