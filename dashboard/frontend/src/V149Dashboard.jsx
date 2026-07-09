import StageDashboard from './StageDashboard';

const endpoints = [["Rehearsal Controller", "/api/v149/rehearsal-controller"], ["V148 Baseline", "/api/v149/v148-baseline"], ["Candidate Snapshot", "/api/v149/candidate-snapshot"], ["Risk Snapshot", "/api/v149/risk-snapshot"], ["Abstention Snapshot", "/api/v149/abstention-snapshot"], ["Hypothetical Order Summary", "/api/v149/hypothetical-order-summary"], ["Hypothetical Reconcile Path", "/api/v149/hypothetical-reconcile-path"], ["Expected Forensic Fields", "/api/v149/expected-forensic-fields"], ["No Broker Payload Proof", "/api/v149/no-broker-payload-proof"], ["No Submit Cancel Proof", "/api/v149/no-submit-cancel-proof"], ["No Account Private Data Proof", "/api/v149/no-account-private-data-proof"], ["Readiness Governor", "/api/v149/readiness-governor"], ["Execution Lock", "/api/v149/execution-lock"], ["Mission State", "/api/v149/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Rehearsal Spine", "rehearsal_controller_status"], ["Broker Contacted", "broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V149Dashboard() {
  return <StageDashboard title="Dummy V149 Production Pilot Rehearsal Spine" endpoints={endpoints} missionKey="dummy_mission_state_report_v135" summaryFields={summaryFields} />;
}
