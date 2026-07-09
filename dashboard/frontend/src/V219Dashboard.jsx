import StageDashboard from './StageDashboard';

const endpoints = [["Hardened Live Proof Execution Harness Controller", "/api/v219/hardened-live-proof-execution-harness-controller"], ["V218 Baseline", "/api/v219/v218-baseline"], ["Arming Prerequisite", "/api/v219/arming-prerequisite"], ["Proof Approval Validator", "/api/v219/proof-approval-validator"], ["Authority Armable Prerequisite", "/api/v219/authority-armable-prerequisite"], ["Cli Env Gate", "/api/v219/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v219/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v219/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v219/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v219/limit-only-proof"], ["No Market Order Proof", "/api/v219/no-market-order-proof"], ["Max One Attempt Guard", "/api/v219/max-one-attempt-guard"], ["Proof Lock", "/api/v219/proof-lock"], ["No Repeat Submit Proof", "/api/v219/no-repeat-submit-proof"], ["Readiness Governor", "/api/v219/readiness-governor"], ["Execution Lock", "/api/v219/execution-lock"], ["Mission State", "/api/v219/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Harness", "hardened_live_proof_execution_harness_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V219Dashboard() {
  return <StageDashboard title="Dummy V219 Hardened Live Proof Execution Harness Full Auth Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v205" summaryFields={summaryFields} />;
}
