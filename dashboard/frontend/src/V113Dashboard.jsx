import StageDashboard from './StageDashboard';

const endpoints = [
  ['Session Canary Controller', '/api/v113/session-canary-controller'],
  ['V112 Baseline', '/api/v113/v112-baseline'],
  ['Session Approval Validator', '/api/v113/session-approval-validator'],
  ['Per Order Approval Mode', '/api/v113/per-order-approval-mode'],
  ['Max Session Order Count Guard', '/api/v113/max-session-order-count-guard'],
  ['Livebrokerfirewall Only Proof', '/api/v113/livebrokerfirewall-only-proof'],
  ['Limit Only Proof', '/api/v113/limit-only-proof'],
  ['No Market Order Proof', '/api/v113/no-market-order-proof'],
  ['Session Autolock', '/api/v113/session-autolock'],
  ['No Repeat Beyond Limit Proof', '/api/v113/no-repeat-beyond-limit-proof'],
  ['Readiness Governor', '/api/v113/readiness-governor'],
  ['Execution Lock', '/api/v113/execution-lock'],
  ['Mission State', '/api/v113/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Session Canary', 'session_canary_controller_status'],
  ['Session Live Orders', 'session_live_orders'],
  ['Broker Contacted', 'real_broker_contacted'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V113Dashboard() {
  return <StageDashboard title='Dummy V113 Controlled Live Session Canary' endpoints={endpoints} missionKey='dummy_mission_state_report_v99' summaryFields={summaryFields} />;
}
