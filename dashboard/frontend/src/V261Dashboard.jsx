import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Final Harness Controller", "/api/v261/execute-once-final-harness-controller"], ["V260 Baseline", "/api/v261/v260-baseline"], ["Freeze Prerequisite", "/api/v261/freeze-prerequisite"], ["Proof Approval Validator", "/api/v261/proof-approval-validator"], ["Cli Env Gate", "/api/v261/cli-env-gate"], ["Mode Live Authorized Prerequisite", "/api/v261/mode-live-authorized-prerequisite"], ["Proof Target Guard", "/api/v261/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v261/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v261/limit-only-proof"], ["No Market Order Proof", "/api/v261/no-market-order-proof"], ["Max One Attempt Guard", "/api/v261/max-one-attempt-guard"], ["Proof Lock", "/api/v261/proof-lock"], ["No Repeat Submit Proof", "/api/v261/no-repeat-submit-proof"], ["No Direct Broker Bypass Proof", "/api/v261/no-direct-broker-bypass-proof"], ["Readiness Governor", "/api/v261/readiness-governor"], ["Execution Lock", "/api/v261/execution-lock"], ["Mission State", "/api/v261/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execute-Once Final", "execute_once_final_harness_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V261Dashboard() {
  return <StageDashboard title="Dummy V261 Execute Once Final Harness V4 Full Auth Only" endpoints={endpoints} missionKey="dummy_mission_state_report_v247" summaryFields={summaryFields} />;
}
