import StageDashboard from './StageDashboard';

const endpoints = [["Live Proof Blocker Controller", "/api/v185/live-proof-blocker-controller"], ["V184 Baseline", "/api/v185/v184-baseline"], ["Blocker Classifier", "/api/v185/blocker-classifier"], ["Controlled Operation Session Approval Blocker", "/api/v185/controlled-operation-session-approval-blocker"], ["Pilot Session Proof Blocker", "/api/v185/pilot-session-proof-blocker"], ["Live Submit Caps Blocker", "/api/v185/live-submit-caps-blocker"], ["Firewall Adapter Blocker", "/api/v185/firewall-adapter-blocker"], ["Autonomy Scale Approval Blocker", "/api/v185/autonomy-scale-approval-blocker"], ["Next Action Matrix", "/api/v185/next-action-matrix"], ["No Submit Proof", "/api/v185/no-submit-proof"], ["No Broker Contact Proof", "/api/v185/no-broker-contact-proof"], ["No Approval File Write Proof", "/api/v185/no-approval-file-write-proof"], ["Readiness Governor", "/api/v185/readiness-governor"], ["Execution Lock", "/api/v185/execution-lock"], ["Mission State", "/api/v185/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Blocker Audit", "live_proof_blocker_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V185Dashboard() {
  return <StageDashboard title="Dummy V185 Live-Proof Blocker Closure V6" endpoints={endpoints} missionKey="dummy_mission_state_report_v171" summaryFields={summaryFields} />;
}
