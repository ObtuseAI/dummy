import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Forensic Autopipeline V5", "/api/v291/reconcile-forensic-autopipeline-v5"], ["V290 Baseline", "/api/v291/v290-baseline"], ["Forensic Review", "/api/v291/forensic-review"], ["No New Order Proof", "/api/v291/no-new-order-proof"], ["No Private Data Leak Proof", "/api/v291/no-private-data-leak-proof"], ["No Broker Contact Proof", "/api/v291/no-broker-contact-proof"], ["Readiness Governor", "/api/v291/readiness-governor"], ["Execution Lock", "/api/v291/execution-lock"], ["Mission State", "/api/v291/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Autopipeline", "reconcile_forensic_autopipeline_v5_controller_status"], ["Fill State", "fill_state"], ["Next Action", "current_next_action"]];

export default function V291Dashboard() {
  return <StageDashboard title="Dummy V291 Reconcile Forensic Autopipeline V5" endpoints={endpoints} missionKey="dummy_mission_state_report_v291" summaryFields={summaryFields} />;
}
