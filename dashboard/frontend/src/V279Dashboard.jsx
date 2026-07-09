import StageDashboard from './StageDashboard';

const endpoints = [["Live Proof Attempt Monitor", "/api/v279/live-proof-attempt-monitor"], ["V278 Baseline", "/api/v279/v278-baseline"], ["Attempt Classification", "/api/v279/attempt-classification"], ["No New Order Proof", "/api/v279/no-new-order-proof"], ["No Private Data Leak Proof", "/api/v279/no-private-data-leak-proof"], ["No Broker Contact Proof", "/api/v279/no-broker-contact-proof"], ["Readiness Governor", "/api/v279/readiness-governor"], ["Execution Lock", "/api/v279/execution-lock"], ["Mission State", "/api/v279/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Monitor", "live_proof_attempt_monitor_controller_status"], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]];

export default function V279Dashboard() {
  return <StageDashboard title="Dummy V279 Live-Proof Attempt Monitor" endpoints={endpoints} missionKey="dummy_mission_state_report_v279" summaryFields={summaryFields} />;
}
