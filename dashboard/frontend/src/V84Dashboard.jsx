import StageDashboard from './StageDashboard';

const endpoints = [
  ['Session Governor', '/api/v84/session-governor'],
  ['V83 Baseline', '/api/v84/v83-baseline'],
  ['Session Start Stop Rules', '/api/v84/session-start-stop-rules'],
  ['Per Order Approval Mode', '/api/v84/per-order-approval-mode'],
  ['Daily Budget Lock', '/api/v84/daily-budget-lock'],
  ['Exposure Lock', '/api/v84/exposure-lock'],
  ['Drift Lock', '/api/v84/drift-lock'],
  ['No Trade Abstention Governor', '/api/v84/no-trade-abstention-governor'],
  ['Live Edge Degradation Monitor', '/api/v84/live-edge-degradation-monitor'],
  ['Broker Failure Mode Policy', '/api/v84/broker-failure-mode-policy'],
  ['Reconcile Requirement', '/api/v84/reconcile-requirement'],
  ['Audit Ledger Requirement', '/api/v84/audit-ledger-requirement'],
  ['Production Readiness Checklist', '/api/v84/production-readiness-checklist'],
  ['Readiness Governor', '/api/v84/readiness-governor'],
  ['Execution Lock', '/api/v84/execution-lock'],
  ['Mission State', '/api/v84/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Production Readiness', 'production_readiness_checklist_status'],
  ['Autonomous Trading', 'autonomous_trading_enabled'],
  ['Per-Order Approval', 'per_order_approval_mode_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V84Dashboard() {
  return <StageDashboard title="Dummy V84 Session Governor & Production Readiness Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v70" summaryFields={summaryFields} />;
}
