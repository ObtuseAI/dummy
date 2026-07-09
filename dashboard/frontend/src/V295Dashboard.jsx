import StageDashboard from './StageDashboard';

const endpoints = [["Real Proof Dependency Cutoff Baseline", "/api/v295/real-proof-dependency-cutoff-baseline"], ["V294 Baseline", "/api/v295/v294-baseline"], ["Fork Classification", "/api/v295/fork-classification"], ["Canonical Next Action List", "/api/v295/canonical-next-action-list"], ["No Submit Proof", "/api/v295/no-submit-proof"], ["No Broker Contact Proof", "/api/v295/no-broker-contact-proof"], ["Readiness Governor", "/api/v295/readiness-governor"], ["Execution Lock", "/api/v295/execution-lock"], ["Mission State", "/api/v295/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Cutoff", "real_proof_dependency_cutoff_baseline_controller_status"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V295Dashboard() {
  return <StageDashboard title="Dummy V295 Real-Proof Dependency Cutoff Baseline" endpoints={endpoints} missionKey="dummy_mission_state_report_v295" summaryFields={summaryFields} />;
}
