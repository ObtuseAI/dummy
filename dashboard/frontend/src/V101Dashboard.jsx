import StageDashboard from './StageDashboard';

const endpoints = [
  ['Forensic Review Controller', '/api/v101/forensic-review-controller'],
  ['V100 Baseline', '/api/v101/v100-baseline'],
  ['Fill Quality Review', '/api/v101/fill-quality-review'],
  ['Reject Cancel Review', '/api/v101/reject-cancel-review'],
  ['Latency Review', '/api/v101/latency-review'],
  ['Slippage Review', '/api/v101/slippage-review'],
  ['Fee Review', '/api/v101/fee-review'],
  ['Forecast Vs Fill Reality', '/api/v101/forecast-vs-fill-reality'],
  ['Evidence To Execution Tieout', '/api/v101/evidence-to-execution-tieout'],
  ['Risk Note', '/api/v101/risk-note'],
  ['No New Order Proof', '/api/v101/no-new-order-proof'],
  ['Readiness Governor', '/api/v101/readiness-governor'],
  ['Execution Lock', '/api/v101/execution-lock'],
  ['Mission State', '/api/v101/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Forensic Review', 'forensic_review_controller_status'],
  ['Forecast-vs-Fill', 'forecast_vs_fill_reality_status'],
  ['No-New-Order', 'no_new_order_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V101Dashboard() {
  return <StageDashboard title="Dummy V101 Order 1 Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v87" summaryFields={summaryFields} />;
}
