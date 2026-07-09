import StageDashboard from './StageDashboard';

const endpoints = [["Activation Cockpit", "/api/v207/activation-cockpit"], ["V206 Baseline", "/api/v207/v206-baseline"], ["Blocker List", "/api/v207/blocker-list"], ["Next Operator Actions", "/api/v207/next-operator-actions"], ["Completion Percentages", "/api/v207/completion-percentages"], ["Authority Status", "/api/v207/authority-status"], ["Live Proof Status", "/api/v207/live-proof-status"], ["Reconcile Forensic Status", "/api/v207/reconcile-forensic-status"], ["Scale Autonomy Status", "/api/v207/scale-autonomy-status"], ["Safe Mode Status", "/api/v207/safe-mode-status"], ["No Ui Submit Proof", "/api/v207/no-ui-submit-proof"], ["No Ui Config Write Proof", "/api/v207/no-ui-config-write-proof"], ["Readiness Governor", "/api/v207/readiness-governor"], ["Execution Lock", "/api/v207/execution-lock"], ["Mission State", "/api/v207/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Cockpit", "cockpit_controller_status"], ["UI Submit Enabled", "ui_submit_enabled"], ["UI Config Write Enabled", "ui_config_write_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V207Dashboard() {
  return <StageDashboard title="Dummy V207 Activation Cockpit" endpoints={endpoints} missionKey="dummy_mission_state_report_v193" summaryFields={summaryFields} />;
}
