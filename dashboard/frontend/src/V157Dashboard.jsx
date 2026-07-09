import StageDashboard from './StageDashboard';

const endpoints = [["Config Audit Controller", "/api/v157/config-audit-controller"], ["V156 Baseline", "/api/v157/v156-baseline"], ["Live Submit Config Parser", "/api/v157/live-submit-config-parser"], ["Caps Config Parser", "/api/v157/caps-config-parser"], ["Hash Before After", "/api/v157/hash-before-after"], ["Enabled Status Check", "/api/v157/enabled-status-check"], ["Operator Metadata Check", "/api/v157/operator-metadata-check"], ["Max Order Size Check", "/api/v157/max-order-size-check"], ["Max Exposure Check", "/api/v157/max-exposure-check"], ["Max Daily Loss Check", "/api/v157/max-daily-loss-check"], ["Kill Switch Status Check", "/api/v157/kill-switch-status-check"], ["Immutable Snapshot Artifact", "/api/v157/immutable-snapshot-artifact"], ["No Live Submit Enable Proof", "/api/v157/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v157/no-caps-modification-proof"], ["No Submit Proof", "/api/v157/no-submit-proof"], ["Readiness Governor", "/api/v157/readiness-governor"], ["Execution Lock", "/api/v157/execution-lock"], ["Mission State", "/api/v157/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Audit", "config_audit_controller_status"], ["Live Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V157Dashboard() {
  return <StageDashboard title="Dummy V157 Live-Submit/Caps Confirmation Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v143" summaryFields={summaryFields} />;
}
