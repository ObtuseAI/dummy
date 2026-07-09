import StageDashboard from './StageDashboard';

const endpoints = [["Dry Session Controller", "/api/v173/dry-session-controller"], ["V172 Baseline", "/api/v173/v172-baseline"], ["Dry Session Id", "/api/v173/dry-session-id"], ["Candidate Sequence Snapshot", "/api/v173/candidate-sequence-snapshot"], ["Risk Gate Sequence", "/api/v173/risk-gate-sequence"], ["Abstention Gate Sequence", "/api/v173/abstention-gate-sequence"], ["Hypothetical Per Order Approval Checks", "/api/v173/hypothetical-per-order-approval-checks"], ["Hypothetical Reconcile Path", "/api/v173/hypothetical-reconcile-path"], ["Hypothetical Forensic Schema", "/api/v173/hypothetical-forensic-schema"], ["Dry Live Mode Firewall Proof", "/api/v173/dry-live-mode-firewall-proof"], ["No Broker Payload Proof", "/api/v173/no-broker-payload-proof"], ["No Submit Cancel Proof", "/api/v173/no-submit-cancel-proof"], ["No Account Private Data Proof", "/api/v173/no-account-private-data-proof"], ["No Scale Proof", "/api/v173/no-scale-proof"], ["No Autonomy Proof", "/api/v173/no-autonomy-proof"], ["Readiness Governor", "/api/v173/readiness-governor"], ["Execution Lock", "/api/v173/execution-lock"], ["Mission State", "/api/v173/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry Session", "dry_session_controller_status"], ["Broker Contacted", "broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V173Dashboard() {
  return <StageDashboard title="Dummy V173 Controlled Operation Dry Session" endpoints={endpoints} missionKey="dummy_mission_state_report_v159" summaryFields={summaryFields} />;
}
