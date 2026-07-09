import StageDashboard from './StageDashboard';

const endpoints = [["Post Proof Reconcile Forensic Launcher", "/api/v280/post-proof-reconcile-forensic-launcher"], ["V279 Baseline", "/api/v280/v279-baseline"], ["Launcher Steps", "/api/v280/launcher-steps"], ["No New Order Proof", "/api/v280/no-new-order-proof"], ["No Broker Contact Proof", "/api/v280/no-broker-contact-proof"], ["Readiness Governor", "/api/v280/readiness-governor"], ["Execution Lock", "/api/v280/execution-lock"], ["Mission State", "/api/v280/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Launcher", "post_proof_reconcile_forensic_launcher_controller_status"], ["Next Action", "current_next_action"]];

export default function V280Dashboard() {
  return <StageDashboard title="Dummy V280 Post-Proof Reconcile Forensic Launcher" endpoints={endpoints} missionKey="dummy_mission_state_report_v280" summaryFields={summaryFields} />;
}
