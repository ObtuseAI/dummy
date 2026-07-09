import StageDashboard from './StageDashboard';

const endpoints = [["Config Quorum Controller", "/api/v196/config-quorum-controller"], ["V195 Baseline", "/api/v196/v195-baseline"], ["Live Submit Before After Hash", "/api/v196/live-submit-before-after-hash"], ["Caps Before After Hash", "/api/v196/caps-before-after-hash"], ["Operator Metadata Validation", "/api/v196/operator-metadata-validation"], ["Enabled Status Validation", "/api/v196/enabled-status-validation"], ["Max Order Size Validation", "/api/v196/max-order-size-validation"], ["Max Exposure Validation", "/api/v196/max-exposure-validation"], ["Max Daily Loss Validation", "/api/v196/max-daily-loss-validation"], ["Kill Switch Validation", "/api/v196/kill-switch-validation"], ["Session Limit Validation", "/api/v196/session-limit-validation"], ["No Live Submit Enable Proof", "/api/v196/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v196/no-caps-modification-proof"], ["No Submit Proof", "/api/v196/no-submit-proof"], ["Readiness Governor", "/api/v196/readiness-governor"], ["Execution Lock", "/api/v196/execution-lock"], ["Mission State", "/api/v196/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Quorum", "config_quorum_controller_status"], ["Live Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V196Dashboard() {
  return <StageDashboard title="Dummy V196 Operator Live Config/Caps Immutable Quorum" endpoints={endpoints} missionKey="dummy_mission_state_report_v182" summaryFields={summaryFields} />;
}
