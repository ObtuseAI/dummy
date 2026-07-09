import StageDashboard from './StageDashboard';

const endpoints = [["External Live Submit Caps State Verifier Controller", "/api/v268/external-live-submit-caps-state-verifier-controller"], ["V267 Baseline", "/api/v268/v267-baseline"], ["Live Submit Checks", "/api/v268/live-submit-checks"], ["Caps Checks", "/api/v268/caps-checks"], ["Kill Switch Check", "/api/v268/kill-switch-check"], ["Live Submit Hash Check", "/api/v268/live-submit-hash-check"], ["Caps Hash Check", "/api/v268/caps-hash-check"], ["Failure Code", "/api/v268/failure-code"], ["No Live Submit Enable Proof", "/api/v268/no-live-submit-enable-proof"], ["No Caps Modification Proof", "/api/v268/no-caps-modification-proof"], ["No Submit Proof", "/api/v268/no-submit-proof"], ["Readiness Governor", "/api/v268/readiness-governor"], ["Execution Lock", "/api/v268/execution-lock"], ["Mission State", "/api/v268/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Caps State Verifier", "external_live_submit_caps_state_verifier_controller_status"], ["Live-Submit Changed", "live_submit_changed"], ["Caps Changed", "caps_changed"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V268Dashboard() {
  return <StageDashboard title="Dummy V268 External Live Submit Caps State Verifier Immutable" endpoints={endpoints} missionKey="dummy_mission_state_report_v254" summaryFields={summaryFields} />;
}
