import StageDashboard from './StageDashboard';

const endpoints = [["Proof Starvation Stop Rule", "/api/v303/proof-starvation-stop-rule"], ["V302 Baseline", "/api/v303/v302-baseline"], ["Starvation Detection", "/api/v303/starvation-detection"], ["Recommendation", "/api/v303/recommendation"], ["No Submit Proof", "/api/v303/no-submit-proof"], ["No Broker Contact Proof", "/api/v303/no-broker-contact-proof"], ["No Scale Proof", "/api/v303/no-scale-proof"], ["No Autonomy Proof", "/api/v303/no-autonomy-proof"], ["Readiness Governor", "/api/v303/readiness-governor"], ["Execution Lock", "/api/v303/execution-lock"], ["Mission State", "/api/v303/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Stop Rule", "proof_starvation_stop_rule_controller_status"], ["State", "starvation_state"], ["Next Action", "current_next_action"]];

export default function V303Dashboard() {
  return <StageDashboard title="Dummy V303 Proof-Starvation Stop Rule" endpoints={endpoints} missionKey="dummy_mission_state_report_v303" summaryFields={summaryFields} />;
}
