import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 1 Canary Controller', '/api/v99/order-1-canary-controller'],
  ['V98 Baseline', '/api/v99/v98-baseline'],
  ['Order 1 Approval Validator', '/api/v99/order-1-approval-validator'],
  ['Pre Submit Checklist', '/api/v99/pre-submit-checklist'],
  ['Single Submit Guard', '/api/v99/single-submit-guard'],
  ['Livebrokerfirewall Submit Adapter', '/api/v99/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v99/post-submit-auto-lock'],
  ['Audit Ledger', '/api/v99/audit-ledger'],
  ['Readiness Governor', '/api/v99/readiness-governor'],
  ['Execution Lock', '/api/v99/execution-lock'],
  ['Mission State', '/api/v99/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 1 Canary', 'order_1_canary_controller_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V99Dashboard() {
  return <StageDashboard title="Dummy V99 Campaign Order 1 Live Canary" endpoints={endpoints} missionKey="dummy_mission_state_report_v85" summaryFields={summaryFields} />;
}
