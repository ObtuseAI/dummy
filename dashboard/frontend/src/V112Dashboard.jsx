import StageDashboard from './StageDashboard';

const endpoints = [
  ['Session Governor Controller', '/api/v112/session-governor-controller'],
  ['V111 Baseline', '/api/v112/v111-baseline'],
  ['Session Start Stop Rules', '/api/v112/session-start-stop-rules'],
  ['Per Order Approval Mode', '/api/v112/per-order-approval-mode'],
  ['Max Session Order Count', '/api/v112/max-session-order-count'],
  ['Daily Budget Lock', '/api/v112/daily-budget-lock'],
  ['Exposure Lock', '/api/v112/exposure-lock'],
  ['Drift Lock', '/api/v112/drift-lock'],
  ['Cooldown Lock', '/api/v112/cooldown-lock'],
  ['Kill Switch', '/api/v112/kill-switch'],
  ['Broker Failure Mode Policy', '/api/v112/broker-failure-mode-policy'],
  ['Reconcile Requirement', '/api/v112/reconcile-requirement'],
  ['No Auto Submit Proof', '/api/v112/no-auto-submit-proof'],
  ['Readiness Governor', '/api/v112/readiness-governor'],
  ['Execution Lock', '/api/v112/execution-lock'],
  ['Mission State', '/api/v112/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Session Governor', 'session_governor_status'],
  ['Session Live Orders', 'session_live_orders'],
  ['Per-Order Mode', 'per_order_approval_mode'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V112Dashboard() {
  return <StageDashboard title='Dummy V112 Session Level Live Governor' endpoints={endpoints} missionKey='dummy_mission_state_report_v98' summaryFields={summaryFields} />;
}
