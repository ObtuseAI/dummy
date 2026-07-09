import StageDashboard from './StageDashboard';

const endpoints = [
  ['Approval Validator Controller', '/api/v96/approval-validator-controller'],
  ['V95 Baseline', '/api/v96/v95-baseline'],
  ['Campaign Approval Validator', '/api/v96/campaign-approval-validator'],
  ['Order 1 Approval Validator', '/api/v96/order-1-approval-validator'],
  ['Scope Expiration Maxone Checks', '/api/v96/scope-expiration-maxone-checks'],
  ['Approval Hash Ledger', '/api/v96/approval-hash-ledger'],
  ['No Raw Phrase Leakage Proof', '/api/v96/no-raw-phrase-leakage-proof'],
  ['No Submit Proof', '/api/v96/no-submit-proof'],
  ['Readiness Governor', '/api/v96/readiness-governor'],
  ['Execution Lock', '/api/v96/execution-lock'],
  ['Mission State', '/api/v96/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Validator', 'approval_validator_controller_status'],
  ['Campaign Approval', 'campaign_approval_validator_status'],
  ['Order 1 Approval', 'order_1_approval_validator_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V96Dashboard() {
  return <StageDashboard title="Dummy V96 Campaign & Order 1 Approval Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v82" summaryFields={summaryFields} />;
}
