import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 2 Canary Controller', '/api/v103/order-2-canary-controller'],
  ['V102 Baseline', '/api/v103/v102-baseline'],
  ['Order 2 Approval Validator', '/api/v103/order-2-approval-validator'],
  ['Stronger Risk Threshold Validator', '/api/v103/stronger-risk-threshold-validator'],
  ['Single Submit Guard', '/api/v103/single-submit-guard'],
  ['Livebrokerfirewall Submit Adapter', '/api/v103/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v103/post-submit-auto-lock'],
  ['Readiness Governor', '/api/v103/readiness-governor'],
  ['Execution Lock', '/api/v103/execution-lock'],
  ['Mission State', '/api/v103/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 2 Canary', 'order_2_canary_controller_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V103Dashboard() {
  return <StageDashboard title="Dummy V103 Campaign Order 2 Live Canary" endpoints={endpoints} missionKey="dummy_mission_state_report_v89" summaryFields={summaryFields} />;
}
