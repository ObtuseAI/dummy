import StageDashboard from './StageDashboard';

const endpoints = [
  ['Forensic Review Controller', '/api/v79/forensic-review-controller'],
  ['V78 Baseline', '/api/v79/v78-baseline'],
  ['Fill Quality Review', '/api/v79/fill-quality-review'],
  ['Reject Cancel Quality Review', '/api/v79/reject-cancel-quality-review'],
  ['Latency Review', '/api/v79/latency-review'],
  ['Slippage Review', '/api/v79/slippage-review'],
  ['Fee Review', '/api/v79/fee-review'],
  ['Forecast Vs Fill Reality Check', '/api/v79/forecast-vs-fill-reality-check'],
  ['Evidence To Execution Tieout', '/api/v79/evidence-to-execution-tieout'],
  ['No Repeat Order Proof', '/api/v79/no-repeat-order-proof'],
  ['Risk Note', '/api/v79/risk-note'],
  ['Readiness Governor', '/api/v79/readiness-governor'],
  ['Execution Lock', '/api/v79/execution-lock'],
  ['Mission State', '/api/v79/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Fill Quality', 'fill_quality_review_status'],
  ['Forecast-vs-Fill', 'forecast_vs_fill_reality_check_status'],
  ['No-Repeat-Order', 'no_repeat_order_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V79Dashboard() {
  return <StageDashboard title="Dummy V79 First Live Canary Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v65" summaryFields={summaryFields} />;
}
