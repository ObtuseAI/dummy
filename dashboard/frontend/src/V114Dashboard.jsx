import StageDashboard from './StageDashboard';

const endpoints = [
  ['Session Reconcile Controller', '/api/v114/session-reconcile-controller'],
  ['V113 Baseline', '/api/v114/v113-baseline'],
  ['Order State Parser', '/api/v114/order-state-parser'],
  ['Fill Reject Cancel Summary', '/api/v114/fill-reject-cancel-summary'],
  ['Idempotency Check', '/api/v114/idempotency-check'],
  ['No Repeat Session Proof', '/api/v114/no-repeat-session-proof'],
  ['Session Forensic Capture', '/api/v114/session-forensic-capture'],
  ['Slippage Latency Fee Buckets', '/api/v114/slippage-latency-fee-buckets'],
  ['No Private Data Leakage Proof', '/api/v114/no-private-data-leakage-proof'],
  ['Session Autolock', '/api/v114/session-autolock'],
  ['Readiness Governor', '/api/v114/readiness-governor'],
  ['Execution Lock', '/api/v114/execution-lock'],
  ['Mission State', '/api/v114/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Session Reconcile', 'session_reconcile_controller_status'],
  ['Session Live Orders', 'session_live_orders'],
  ['Auto-Lock', 'session_autolock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V114Dashboard() {
  return <StageDashboard title='Dummy V114 Live Session Reconcile & Auto-Lock' endpoints={endpoints} missionKey='dummy_mission_state_report_v100' summaryFields={summaryFields} />;
}
