import StageDashboard from './StageDashboard';

const endpoints = [["Armable Quorum Doctor Controller", "/api/v240/armable-quorum-doctor-controller"], ["V239 Baseline", "/api/v240/v239-baseline"], ["Manifest Doctor Readback", "/api/v240/manifest-doctor-readback"], ["Config Doctor Readback", "/api/v240/config-doctor-readback"], ["Adapter Doctor Readback", "/api/v240/adapter-doctor-readback"], ["Broker Readonly Doctor Readback", "/api/v240/broker-readonly-doctor-readback"], ["Dry Validation Readback", "/api/v240/dry-validation-readback"], ["Env Gate Check", "/api/v240/env-gate-check"], ["Mode Live Authorized Check", "/api/v240/mode-live-authorized-check"], ["Proof Target Check", "/api/v240/proof-target-check"], ["Candidate Risk Abstention Check", "/api/v240/candidate-risk-abstention-check"], ["Proof Lock Check", "/api/v240/proof-lock-check"], ["Resolver Explanation", "/api/v240/resolver-explanation"], ["No Submit Proof", "/api/v240/no-submit-proof"], ["No Broker Contact Proof", "/api/v240/no-broker-contact-proof"], ["Readiness Governor", "/api/v240/readiness-governor"], ["Execution Lock", "/api/v240/execution-lock"], ["Mission State", "/api/v240/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Quorum Doctor", "armable_quorum_doctor_controller_status"], ["Resolver Explanation", "resolver_explanation"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V240Dashboard() {
  return <StageDashboard title="Dummy V240 Armable Quorum Doctor Resolver Explanation No Submit" endpoints={endpoints} missionKey="dummy_mission_state_report_v226" summaryFields={summaryFields} />;
}
