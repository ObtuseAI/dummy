import StageDashboard from './StageDashboard';

const endpoints = [["Live Submit Caps Doctor Controller", "/api/v237/live-submit-caps-doctor-controller"], ["V236 Baseline", "/api/v237/v236-baseline"], ["Live Submit File Check", "/api/v237/live-submit-file-check"], ["Live Submit Enabled Check", "/api/v237/live-submit-enabled-check"], ["Live Submit Operator Metadata Check", "/api/v237/live-submit-operator-metadata-check"], ["Live Submit Hash Check", "/api/v237/live-submit-hash-check"], ["Caps File Check", "/api/v237/caps-file-check"], ["Caps Limits Check", "/api/v237/caps-limits-check"], ["Caps Kill Switch Check", "/api/v237/caps-kill-switch-check"], ["Caps Hash Check", "/api/v237/caps-hash-check"], ["Failure Code", "/api/v237/failure-code"], ["No Live Submit Enable Proof", "/api/v237/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v237/no-caps-modification-proof"], ["No Submit Proof", "/api/v237/no-submit-proof"], ["Readiness Governor", "/api/v237/readiness-governor"], ["Execution Lock", "/api/v237/execution-lock"], ["Mission State", "/api/v237/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Doctor", "live_submit_caps_doctor_controller_status"], ["Live-Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V237Dashboard() {
  return <StageDashboard title="Dummy V237 Live Submit Caps Doctor Readonly Immutable" endpoints={endpoints} missionKey="dummy_mission_state_report_v223" summaryFields={summaryFields} />;
}
