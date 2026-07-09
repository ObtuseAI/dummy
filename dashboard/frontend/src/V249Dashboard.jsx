import StageDashboard from './StageDashboard';

const endpoints = [["Live Submit Caps Rehearsal Controller", "/api/v249/live-submit-caps-rehearsal-controller"], ["V248 Baseline", "/api/v249/v248-baseline"], ["Rehearsal Cases", "/api/v249/rehearsal-cases"], ["Live Submit Hash Check", "/api/v249/live-submit-hash-check"], ["Caps Hash Check", "/api/v249/caps-hash-check"], ["Failure Code", "/api/v249/failure-code"], ["No Live Submit Enable Proof", "/api/v249/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v249/no-caps-modification-proof"], ["No Submit Proof", "/api/v249/no-submit-proof"], ["Readiness Governor", "/api/v249/readiness-governor"], ["Execution Lock", "/api/v249/execution-lock"], ["Mission State", "/api/v249/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Rehearsal", "live_submit_caps_rehearsal_controller_status"], ["Live-Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V249Dashboard() {
  return <StageDashboard title="Dummy V249 Live Submit Caps Rehearsal Auditor Immutable" endpoints={endpoints} missionKey="dummy_mission_state_report_v235" summaryFields={summaryFields} />;
}
