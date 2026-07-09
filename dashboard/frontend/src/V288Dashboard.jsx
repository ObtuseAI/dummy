import StageDashboard from './StageDashboard';

const endpoints = [["Live Proof No Surprises Precheck", "/api/v288/live-proof-no-surprises-precheck"], ["V287 Baseline", "/api/v288/v287-baseline"], ["Precheck Matrix", "/api/v288/precheck-matrix"], ["No Submit Proof", "/api/v288/no-submit-proof"], ["No Broker Contact Proof", "/api/v288/no-broker-contact-proof"], ["Readiness Governor", "/api/v288/readiness-governor"], ["Execution Lock", "/api/v288/execution-lock"], ["Mission State", "/api/v288/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Precheck", "live_proof_no_surprises_precheck_controller_status"], ["State", "precheck_state"], ["Next Action", "current_next_action"]];

export default function V288Dashboard() {
  return <StageDashboard title="Dummy V288 Live-Proof No-Surprises Precheck" endpoints={endpoints} missionKey="dummy_mission_state_report_v288" summaryFields={summaryFields} />;
}
