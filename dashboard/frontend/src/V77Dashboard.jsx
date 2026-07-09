import StageDashboard from './StageDashboard';

const endpoints = [
  ['Live Canary Controller', '/api/v77/live-canary-controller'],
  ['V76 Baseline', '/api/v77/v76-baseline'],
  ['Exact Approval Validator', '/api/v77/exact-approval-validator'],
  ['Single Submit Guard', '/api/v77/single-submit-guard'],
  ['Livebrokerfirewall Submit Adapter', '/api/v77/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v77/post-submit-auto-lock'],
  ['Audit Ledger', '/api/v77/audit-ledger'],
  ['Readiness Governor', '/api/v77/readiness-governor'],
  ['Execution Lock', '/api/v77/execution-lock'],
  ['Mission State', '/api/v77/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Single-Submit Guard', 'single_submit_guard_status'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V77Dashboard() {
  return <StageDashboard title="Dummy V77 First Tiny Live Limit-Order Canary" endpoints={endpoints} missionKey="dummy_mission_state_report_v63" summaryFields={summaryFields} />;
}
