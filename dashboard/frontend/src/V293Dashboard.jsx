import StageDashboard from './StageDashboard';

const endpoints = [["Real Proof Required Scale Autonomy Wall", "/api/v293/real-proof-required-scale-autonomy-wall"], ["V292 Baseline", "/api/v293/v292-baseline"], ["Proof Classification", "/api/v293/proof-classification"], ["No Submit Proof", "/api/v293/no-submit-proof"], ["No Scale Proof", "/api/v293/no-scale-proof"], ["No Autonomy Proof", "/api/v293/no-autonomy-proof"], ["Readiness Governor", "/api/v293/readiness-governor"], ["Execution Lock", "/api/v293/execution-lock"], ["Mission State", "/api/v293/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Wall", "real_proof_required_scale_autonomy_wall_controller_status"], ["Proof Class", "proof_classification"], ["Next Action", "current_next_action"]];

export default function V293Dashboard() {
  return <StageDashboard title="Dummy V293 Real-Proof-Required Scale Autonomy Wall" endpoints={endpoints} missionKey="dummy_mission_state_report_v293" summaryFields={summaryFields} />;
}
