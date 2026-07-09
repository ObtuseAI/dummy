import StageDashboard from './StageDashboard';

const endpoints = [
  ['Approval Registry Controller', '/api/v86/approval-registry-controller'],
  ['V85 Baseline', '/api/v86/v85-baseline'],
  ['Campaign Approval Validator', '/api/v86/campaign-approval-validator'],
  ['Per Order Approval Validator', '/api/v86/per-order-approval-validator'],
  ['Approval Expiration Scope Maxcount Checks', '/api/v86/approval-expiration-scope-maxcount-checks'],
  ['Approval Hash Ledger', '/api/v86/approval-hash-ledger'],
  ['No Raw Phrase Leakage Proof', '/api/v86/no-raw-phrase-leakage-proof'],
  ['No Submit Proof', '/api/v86/no-submit-proof'],
  ['Readiness Governor', '/api/v86/readiness-governor'],
  ['Execution Lock', '/api/v86/execution-lock'],
  ['Mission State', '/api/v86/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Registry', 'approval_registry_controller_status'],
  ['Campaign Approval', 'campaign_approval_validator_status'],
  ['Per-Order Registry', 'per_order_approval_validator_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V86Dashboard() {
  return <StageDashboard title="Dummy V86 Campaign Approval & Per-Order Registry" endpoints={endpoints} missionKey="dummy_mission_state_report_v72" summaryFields={summaryFields} />;
}
