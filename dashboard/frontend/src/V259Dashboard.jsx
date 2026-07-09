import StageDashboard from './StageDashboard';

const endpoints = [["Live Submit Caps Final Rehearsal Controller", "/api/v259/live-submit-caps-final-rehearsal-controller"], ["V258 Baseline", "/api/v259/v258-baseline"], ["Live Submit Checks", "/api/v259/live-submit-checks"], ["Caps Checks", "/api/v259/caps-checks"], ["Live Submit Hash Check", "/api/v259/live-submit-hash-check"], ["Caps Hash Check", "/api/v259/caps-hash-check"], ["Failure Code", "/api/v259/failure-code"], ["No Live Submit Enable Proof", "/api/v259/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v259/no-caps-modification-proof"], ["No Submit Proof", "/api/v259/no-submit-proof"], ["Readiness Governor", "/api/v259/readiness-governor"], ["Execution Lock", "/api/v259/execution-lock"], ["Mission State", "/api/v259/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Config Final Rehearsal", "live_submit_caps_final_rehearsal_controller_status"], ["Live-Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V259Dashboard() {
  return <StageDashboard title="Dummy V259 Live Submit Caps Final Rehearsal V2 Immutable" endpoints={endpoints} missionKey="dummy_mission_state_report_v245" summaryFields={summaryFields} />;
}
