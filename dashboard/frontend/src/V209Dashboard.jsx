import StageDashboard from './StageDashboard';

const endpoints = [["Live Proof Runner Controller", "/api/v209/live-proof-runner-controller"], ["V208 Baseline", "/api/v209/v208-baseline"], ["Proof Approval Validator", "/api/v209/proof-approval-validator"], ["Authority Armable Prerequisite", "/api/v209/authority-armable-prerequisite"], ["Cli Env Gate", "/api/v209/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v209/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v209/proof-target-guard"], ["Max One Proof Attempt Guard", "/api/v209/max-one-proof-attempt-guard"], ["Livebrokerfirewall Only Proof", "/api/v209/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v209/limit-only-proof"], ["No Market Order Proof", "/api/v209/no-market-order-proof"], ["Proof Lock", "/api/v209/proof-lock"], ["No Repeat Submit Proof", "/api/v209/no-repeat-submit-proof"], ["Readiness Governor", "/api/v209/readiness-governor"], ["Execution Lock", "/api/v209/execution-lock"], ["Mission State", "/api/v209/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Runner", "live_proof_runner_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V209Dashboard() {
  return <StageDashboard title="Dummy V209 Live-Proof Runner Wrapper" endpoints={endpoints} missionKey="dummy_mission_state_report_v195" summaryFields={summaryFields} />;
}
