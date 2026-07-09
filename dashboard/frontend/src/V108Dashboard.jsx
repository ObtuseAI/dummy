import StageDashboard from './StageDashboard';

const endpoints = [
  ['Risk Hardening Controller', '/api/v108/risk-hardening-controller'],
  ['V107 Baseline', '/api/v108/v107-baseline'],
  ['Max Order Size Policy', '/api/v108/max-order-size-policy'],
  ['Max Daily Loss Policy', '/api/v108/max-daily-loss-policy'],
  ['Max Open Exposure Policy', '/api/v108/max-open-exposure-policy'],
  ['Max Concurrent Markets Policy', '/api/v108/max-concurrent-markets-policy'],
  ['Cooldown After Loss', '/api/v108/cooldown-after-loss'],
  ['Cooldown After Reject', '/api/v108/cooldown-after-reject'],
  ['Cooldown After Drift', '/api/v108/cooldown-after-drift'],
  ['Slippage Ceiling', '/api/v108/slippage-ceiling'],
  ['Liquidity Floor', '/api/v108/liquidity-floor'],
  ['Kill Switch', '/api/v108/kill-switch'],
  ['Session Lock', '/api/v108/session-lock'],
  ['Operator Override Requirement', '/api/v108/operator-override-requirement'],
  ['No Scale Proof', '/api/v108/no-scale-proof'],
  ['Readiness Governor', '/api/v108/readiness-governor'],
  ['Execution Lock', '/api/v108/execution-lock'],
  ['Mission State', '/api/v108/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Risk Hardening', 'risk_hardening_controller_status'],
  ['Kill Switch', 'kill_switch_status'],
  ['Caps Modified', 'caps_modified'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V108Dashboard() {
  return <StageDashboard title='Dummy V108 Risk Governor Production Hardening' endpoints={endpoints} missionKey='dummy_mission_state_report_v94' summaryFields={summaryFields} />;
}
