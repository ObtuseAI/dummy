import StageDashboard from './StageDashboard';

const endpoints = [
  ['Blocker Closure Controller', '/api/v85/blocker-closure-controller'],
  ['V84 Baseline', '/api/v85/v84-baseline'],
  ['Campaign Approval Gap', '/api/v85/campaign-approval-gap'],
  ['Per Order Approval Gap', '/api/v85/per-order-approval-gap'],
  ['Live Submit Config Gap', '/api/v85/live-submit-config-gap'],
  ['Caps Gap', '/api/v85/caps-gap'],
  ['Broker Adapter Gap', '/api/v85/broker-adapter-gap'],
  ['Canary Proof Gap', '/api/v85/canary-proof-gap'],
  ['Risk Scaling Gap', '/api/v85/risk-scaling-gap'],
  ['No Auto Submit Proof', '/api/v85/no-auto-submit-proof'],
  ['Readiness Governor', '/api/v85/readiness-governor'],
  ['Execution Lock', '/api/v85/execution-lock'],
  ['Mission State', '/api/v85/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Blocker Closure', 'blocker_closure_controller_status'],
  ['No-Auto-Submit', 'no_auto_submit_proof_status'],
  ['Live Orders', 'live_orders'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V85Dashboard() {
  return <StageDashboard title="Dummy V85 Micro-Campaign Blocker Closure" endpoints={endpoints} missionKey="dummy_mission_state_report_v71" summaryFields={summaryFields} />;
}
