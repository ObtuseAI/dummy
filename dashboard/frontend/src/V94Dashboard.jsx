import StageDashboard from './StageDashboard';

const endpoints = [
  ['Final Campaign Audit Controller', '/api/v94/final-campaign-audit-controller'],
  ['V93 Baseline', '/api/v94/v93-baseline'],
  ['Campaign Outcome Ledger', '/api/v94/campaign-outcome-ledger'],
  ['Fill Reject Cancel Summary', '/api/v94/fill-reject-cancel-summary'],
  ['Slippage Latency Fee Summary', '/api/v94/slippage-latency-fee-summary'],
  ['Edge Degradation Review', '/api/v94/edge-degradation-review'],
  ['Abstention Quality Review', '/api/v94/abstention-quality-review'],
  ['Risk Governor Performance', '/api/v94/risk-governor-performance'],
  ['Kill Switch Session Lock Review', '/api/v94/kill-switch-session-lock-review'],
  ['Scale Recommendation Report', '/api/v94/scale-recommendation-report'],
  ['Production Gate', '/api/v94/production-gate'],
  ['Readiness Governor', '/api/v94/readiness-governor'],
  ['Execution Lock', '/api/v94/execution-lock'],
  ['Mission State', '/api/v94/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Final Audit', 'final_campaign_audit_controller_status'],
  ['Scale Recommendation', 'scale_recommendation'],
  ['Production Gate', 'production_gate_status'],
  ['Autonomous Trading', 'autonomous_trading_enabled'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V94Dashboard() {
  return <StageDashboard title="Dummy V94 Final Audit, Scaling & Production Gate" endpoints={endpoints} missionKey="dummy_mission_state_report_v80" summaryFields={summaryFields} />;
}
