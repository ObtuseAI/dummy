import StageDashboard from './StageDashboard';

const endpoints = [
  ['Campaign Gate Controller', '/api/v82/campaign-gate-controller'],
  ['V81 Baseline', '/api/v82/v81-baseline'],
  ['Campaign Approval Validator', '/api/v82/campaign-approval-validator'],
  ['Per Order Approval Requirement', '/api/v82/per-order-approval-requirement'],
  ['Max Trades Policy', '/api/v82/max-trades-policy'],
  ['Max Daily Loss Policy', '/api/v82/max-daily-loss-policy'],
  ['Max Exposure Policy', '/api/v82/max-exposure-policy'],
  ['Cooldown Policy', '/api/v82/cooldown-policy'],
  ['Drift Lock Policy', '/api/v82/drift-lock-policy'],
  ['Session Lock Policy', '/api/v82/session-lock-policy'],
  ['No Auto Submit Proof', '/api/v82/no-auto-submit-proof'],
  ['Readiness Governor', '/api/v82/readiness-governor'],
  ['Execution Lock', '/api/v82/execution-lock'],
  ['Mission State', '/api/v82/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Per-Order Approval', 'per_order_approval_requirement_status'],
  ['No-Auto-Submit', 'no_auto_submit_proof_status'],
  ['Campaign Orders', 'campaign_live_orders_submitted'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V82Dashboard() {
  return <StageDashboard title="Dummy V82 Micro-Canary Campaign Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v68" summaryFields={summaryFields} />;
}
