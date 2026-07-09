import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Runbook Controller", "/api/v272/execute-once-runbook-controller"], ["V271 Baseline", "/api/v272/v271-baseline"], ["Armability Prerequisite", "/api/v272/armability-prerequisite"], ["Proof Approval Validator", "/api/v272/proof-approval-validator"], ["Cli Env Gate", "/api/v272/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v272/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v272/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v272/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v272/limit-only-proof"], ["No Market Order Proof", "/api/v272/no-market-order-proof"], ["Max One Attempt Guard", "/api/v272/max-one-attempt-guard"], ["Proof Lock", "/api/v272/proof-lock"], ["No Repeat Submit Proof", "/api/v272/no-repeat-submit-proof"], ["No Direct Broker Bypass Proof", "/api/v272/no-direct-broker-bypass-proof"], ["Readiness Governor", "/api/v272/readiness-governor"], ["Execution Lock", "/api/v272/execution-lock"], ["Mission State", "/api/v272/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execute-Once Runbook", "execute_once_runbook_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V272Dashboard() {
  return <StageDashboard title="Dummy V272 Execute Once Runbook Wrapper V5 Full Auth Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v258" summaryFields={summaryFields} />;
}
