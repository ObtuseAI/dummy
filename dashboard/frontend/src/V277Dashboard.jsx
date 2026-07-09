import StageDashboard from './StageDashboard';

const endpoints = [["Final Live Proof Runbook Lock", "/api/v277/final-live-proof-runbook-lock"], ["V276 Baseline", "/api/v277/v276-baseline"], ["Command Sequence", "/api/v277/command-sequence"], ["Env Gate", "/api/v277/env-gate"], ["No Submit Proof", "/api/v277/no-submit-proof"], ["No Broker Contact Proof", "/api/v277/no-broker-contact-proof"], ["Readiness Governor", "/api/v277/readiness-governor"], ["Execution Lock", "/api/v277/execution-lock"], ["Mission State", "/api/v277/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Runbook Lock", "final_live_proof_runbook_lock_controller_status"], ["Next Action", "current_next_action"]];

export default function V277Dashboard() {
  return <StageDashboard title="Dummy V277 Final Live-Proof Runbook Lock" endpoints={endpoints} missionKey="dummy_mission_state_report_v277" summaryFields={summaryFields} />;
}
