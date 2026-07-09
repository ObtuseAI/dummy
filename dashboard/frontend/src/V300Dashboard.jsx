import StageDashboard from './StageDashboard';

const endpoints = [["Reconcile Forensic Auto Orchestrator V6", "/api/v300/reconcile-forensic-auto-orchestrator-v6"], ["V299 Baseline", "/api/v300/v299-baseline"], ["Forensic Review", "/api/v300/forensic-review"], ["No New Order Proof", "/api/v300/no-new-order-proof"], ["No Private Data Leak Proof", "/api/v300/no-private-data-leak-proof"], ["No Broker Contact Proof", "/api/v300/no-broker-contact-proof"], ["Readiness Governor", "/api/v300/readiness-governor"], ["Execution Lock", "/api/v300/execution-lock"], ["Mission State", "/api/v300/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Orchestrator", "reconcile_forensic_auto_orchestrator_v6_controller_status"], ["Fill State", "fill_state"], ["Next Action", "current_next_action"]];

export default function V300Dashboard() {
  return <StageDashboard title="Dummy V300 Reconcile Forensic Auto-Orchestrator V6" endpoints={endpoints} missionKey="dummy_mission_state_report_v300" summaryFields={summaryFields} />;
}
