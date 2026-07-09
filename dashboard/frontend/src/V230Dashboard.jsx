import StageDashboard from './StageDashboard';

const endpoints = [["Live Proof Execution Orchestrator Controller", "/api/v230/live-proof-execution-orchestrator-controller"], ["V229 Baseline", "/api/v230/v229-baseline"], ["Arming Prerequisite", "/api/v230/arming-prerequisite"], ["Proof Approval Validator", "/api/v230/proof-approval-validator"], ["Authority Armable Prerequisite", "/api/v230/authority-armable-prerequisite"], ["Cli Env Gate", "/api/v230/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v230/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v230/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v230/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v230/limit-only-proof"], ["No Market Order Proof", "/api/v230/no-market-order-proof"], ["Max One Attempt Guard", "/api/v230/max-one-attempt-guard"], ["Proof Lock", "/api/v230/proof-lock"], ["No Repeat Submit Proof", "/api/v230/no-repeat-submit-proof"], ["Readiness Governor", "/api/v230/readiness-governor"], ["Execution Lock", "/api/v230/execution-lock"], ["Mission State", "/api/v230/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execution", "live_proof_execution_orchestrator_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V230Dashboard() {
  return <StageDashboard title="Dummy V230 Live Proof Execution Orchestrator Full Authority Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v216" summaryFields={summaryFields} />;
}
