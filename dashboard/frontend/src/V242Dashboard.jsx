import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Harness Controller", "/api/v242/execute-once-harness-controller"], ["V241 Baseline", "/api/v242/v241-baseline"], ["Armable Quorum Prerequisite", "/api/v242/armable-quorum-prerequisite"], ["Proof Approval Validator", "/api/v242/proof-approval-validator"], ["Cli Env Gate", "/api/v242/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v242/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v242/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v242/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v242/limit-only-proof"], ["No Market Order Proof", "/api/v242/no-market-order-proof"], ["Max One Attempt Guard", "/api/v242/max-one-attempt-guard"], ["Proof Lock", "/api/v242/proof-lock"], ["No Repeat Submit Proof", "/api/v242/no-repeat-submit-proof"], ["No Direct Broker Bypass Proof", "/api/v242/no-direct-broker-bypass-proof"], ["Readiness Governor", "/api/v242/readiness-governor"], ["Execution Lock", "/api/v242/execution-lock"], ["Mission State", "/api/v242/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execute-Once Harness", "execute_once_harness_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V242Dashboard() {
  return <StageDashboard title="Dummy V242 Live Proof Execute Once Harness V2 Full Auth Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v228" summaryFields={summaryFields} />;
}
