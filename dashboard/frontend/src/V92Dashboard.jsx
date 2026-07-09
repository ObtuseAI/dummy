import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Review Controller', '/api/v92/reconcile-review-controller'],
  ['V91 Baseline', '/api/v92/v91-baseline'],
  ['Order 2 Outcome Parser', '/api/v92/order-2-outcome-parser'],
  ['Cumulative Campaign Ledger', '/api/v92/cumulative-campaign-ledger'],
  ['Edge Vs Fill Reality Review', '/api/v92/edge-vs-fill-reality-review'],
  ['Slippage Latency Trend', '/api/v92/slippage-latency-trend'],
  ['No Trade Abstention Review', '/api/v92/no-trade-abstention-review'],
  ['Stop Continue Decision', '/api/v92/stop-continue-decision'],
  ['Readiness Governor', '/api/v92/readiness-governor'],
  ['Execution Lock', '/api/v92/execution-lock'],
  ['Mission State', '/api/v92/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Reconcile/Review', 'reconcile_review_controller_status'],
  ['Stop/Continue', 'stop_continue_decision_status'],
  ['Edge vs Fill', 'edge_vs_fill_reality_review_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V92Dashboard() {
  return <StageDashboard title="Dummy V92 Order 2 Reconcile & Stop/Continue" endpoints={endpoints} missionKey="dummy_mission_state_report_v78" summaryFields={summaryFields} />;
}
