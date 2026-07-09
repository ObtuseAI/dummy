import StageDashboard from './StageDashboard';

const endpoints = [
  ['Live Canary Controller', '/api/v70/live-canary-controller'],
  ['V69 Baseline', '/api/v70/v69-baseline'],
  ['Exact Approval Validator', '/api/v70/exact-approval-validator'],
  ['Pre-Submit Checklist', '/api/v70/pre-submit-checklist'],
  ['Single-Submit Guard', '/api/v70/single-submit-guard'],
  ['Idempotency Key', '/api/v70/idempotency-key'],
  ['LiveBrokerFirewall Submit Adapter', '/api/v70/livebrokerfirewall-submit-adapter'],
  ['Post-Submit Auto-Lock', '/api/v70/post-submit-auto-lock'],
  ['Audit Ledger', '/api/v70/audit-ledger'],
  ['Readiness Governor V30', '/api/v70/readiness-governor'],
  ['Execution Lock V29', '/api/v70/execution-lock'],
  ['Mission State V70', '/api/v70/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V69 Baseline', 'v69_baseline_status'],
  ['Controller', 'live_canary_controller_status'],
  ['Pre-Submit Checklist', 'pre_submit_checklist_status'],
  ['Single-Submit Guard', 'single_submit_guard_status'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Real Orders Submitted', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Readiness', 'readiness_governor_v30_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v29_status'],
  ['Next Action', 'current_next_action']
];

export default function V70Dashboard() {
  return <StageDashboard title="Dummy V70 First Tiny Live Limit-Order Canary (Firewall-Only)" endpoints={endpoints} missionKey="dummy_mission_state_report_v56" summaryFields={summaryFields} />;
}
