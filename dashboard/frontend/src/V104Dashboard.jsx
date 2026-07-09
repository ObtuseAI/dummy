import StageDashboard from './StageDashboard';

const endpoints = [
  ['Reconcile Review Controller', '/api/v104/reconcile-review-controller'],
  ['V103 Baseline', '/api/v104/v103-baseline'],
  ['Order 2 Outcome Parser', '/api/v104/order-2-outcome-parser'],
  ['Cumulative Campaign Ledger', '/api/v104/cumulative-campaign-ledger'],
  ['Edge Vs Fill Reality Review', '/api/v104/edge-vs-fill-reality-review'],
  ['Slippage Latency Trend', '/api/v104/slippage-latency-trend'],
  ['No Trade Abstention Review', '/api/v104/no-trade-abstention-review'],
  ['Stop Continue Decision', '/api/v104/stop-continue-decision'],
  ['Readiness Governor', '/api/v104/readiness-governor'],
  ['Execution Lock', '/api/v104/execution-lock'],
  ['Mission State', '/api/v104/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Reconcile/Review', 'reconcile_review_controller_status'],
  ['Stop/Continue', 'stop_continue_decision_status'],
  ['Edge vs Fill', 'edge_vs_fill_reality_review_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V104Dashboard() {
  return <StageDashboard title="Dummy V104 Order 2 Reconcile & Stop/Continue" endpoints={endpoints} missionKey="dummy_mission_state_report_v90" summaryFields={summaryFields} />;
}
