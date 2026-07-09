import StageDashboard from './StageDashboard';

const endpoints = [["Config Snapshot Controller", "/api/v137/config-snapshot-controller"], ["V136 Baseline", "/api/v137/v136-baseline"], ["Live Submit Hash Snapshot", "/api/v137/live-submit-hash-snapshot"], ["Caps Hash Snapshot", "/api/v137/caps-hash-snapshot"], ["Max Order Size", "/api/v137/max-order-size"], ["Max Exposure", "/api/v137/max-exposure"], ["Max Daily Loss", "/api/v137/max-daily-loss"], ["Session Lock", "/api/v137/session-lock"], ["Kill Switch", "/api/v137/kill-switch"], ["No Live Submit Enable Proof", "/api/v137/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v137/no-caps-modification-proof"], ["Readiness Governor", "/api/v137/readiness-governor"], ["Execution Lock", "/api/v137/execution-lock"], ["Mission State", "/api/v137/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Snapshot", "config_snapshot_controller_status"], ["Live Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V137Dashboard() {
  return <StageDashboard title="Dummy V137 Live-Submit & Caps Immutable Snapshot" endpoints={endpoints} missionKey="dummy_mission_state_report_v123" summaryFields={summaryFields} />;
}
