import StageDashboard from './StageDashboard';

const endpoints = [
  ['Order 1 Gate Controller', '/api/v89/order-1-gate-controller'],
  ['V88 Baseline', '/api/v89/v88-baseline'],
  ['Order 1 Approval Validator', '/api/v89/order-1-approval-validator'],
  ['Pre Submit Checklist', '/api/v89/pre-submit-checklist'],
  ['Single Submit Guard', '/api/v89/single-submit-guard'],
  ['Livebrokerfirewall Submit Adapter', '/api/v89/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v89/post-submit-auto-lock'],
  ['Audit Ledger', '/api/v89/audit-ledger'],
  ['Readiness Governor', '/api/v89/readiness-governor'],
  ['Execution Lock', '/api/v89/execution-lock'],
  ['Mission State', '/api/v89/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Order 1 Gate', 'order_1_gate_controller_status'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V89Dashboard() {
  return <StageDashboard title="Dummy V89 Campaign Order 1 Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v75" summaryFields={summaryFields} />;
}
