import StageDashboard from './StageDashboard';

const endpoints = [["First Proof Final Run Baseline", "/api/v285/first-proof-final-run-baseline"], ["V284 Baseline", "/api/v285/v284-baseline"], ["Appliance State Classification", "/api/v285/appliance-state-classification"], ["Canonical Next Action List", "/api/v285/canonical-next-action-list"], ["No Submit Proof", "/api/v285/no-submit-proof"], ["No Broker Contact Proof", "/api/v285/no-broker-contact-proof"], ["Readiness Governor", "/api/v285/readiness-governor"], ["Execution Lock", "/api/v285/execution-lock"], ["Mission State", "/api/v285/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Baseline", "first_proof_final_run_baseline_controller_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V285Dashboard() {
  return <StageDashboard title="Dummy V285 First-Proof Final Run Baseline" endpoints={endpoints} missionKey="dummy_mission_state_report_v285" summaryFields={summaryFields} />;
}
