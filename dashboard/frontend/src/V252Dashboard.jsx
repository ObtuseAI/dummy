import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Dry Fixture Harness Controller", "/api/v252/execute-once-dry-fixture-harness-controller"], ["V251 Baseline", "/api/v252/v251-baseline"], ["Dry Mode Default", "/api/v252/dry-mode-default"], ["Proof Approval Validator", "/api/v252/proof-approval-validator"], ["Cli Env Gate", "/api/v252/cli-env-gate"], ["Proof Target Guard", "/api/v252/proof-target-guard"], ["Livebrokerfirewall Only Proof", "/api/v252/livebrokerfirewall-only-proof"], ["Limit Only Proof", "/api/v252/limit-only-proof"], ["No Market Order Proof", "/api/v252/no-market-order-proof"], ["Max One Attempt Guard", "/api/v252/max-one-attempt-guard"], ["Proof Lock", "/api/v252/proof-lock"], ["No Repeat Submit Proof", "/api/v252/no-repeat-submit-proof"], ["Safety Proven", "/api/v252/safety-proven"], ["Readiness Governor", "/api/v252/readiness-governor"], ["Execution Lock", "/api/v252/execution-lock"], ["Mission State", "/api/v252/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry/Fixture Harness", "execute_once_dry_fixture_harness_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V252Dashboard() {
  return <StageDashboard title="Dummy V252 Execute Once Dry Fixture Harness V3 No Real Orders" endpoints={endpoints} missionKey="dummy_mission_state_report_v238" summaryFields={summaryFields} />;
}
