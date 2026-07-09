import StageDashboard from './StageDashboard';

const endpoints = [
  ['Risk Hardening Controller', '/api/v83/risk-hardening-controller'],
  ['V82 Baseline', '/api/v83/v82-baseline'],
  ['Max Order Size', '/api/v83/max-order-size'],
  ['Max Daily Loss', '/api/v83/max-daily-loss'],
  ['Max Open Exposure', '/api/v83/max-open-exposure'],
  ['Max Concurrent Markets', '/api/v83/max-concurrent-markets'],
  ['Cooldown After Loss', '/api/v83/cooldown-after-loss'],
  ['Cooldown After Reject', '/api/v83/cooldown-after-reject'],
  ['Cooldown After Drift', '/api/v83/cooldown-after-drift'],
  ['Max Slippage', '/api/v83/max-slippage'],
  ['Kill Switch', '/api/v83/kill-switch'],
  ['Session Lock', '/api/v83/session-lock'],
  ['Operator Override Requirement', '/api/v83/operator-override-requirement'],
  ['Scale Step Policy', '/api/v83/scale-step-policy'],
  ['Readiness Governor', '/api/v83/readiness-governor'],
  ['Execution Lock', '/api/v83/execution-lock'],
  ['Mission State', '/api/v83/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Kill-Switch', 'kill_switch_status'],
  ['Session-Lock', 'session_lock_status'],
  ['Scale-Step', 'scale_step_policy_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V83Dashboard() {
  return <StageDashboard title="Dummy V83 Risk Governor Hardening & Scaling Policy" endpoints={endpoints} missionKey="dummy_mission_state_report_v69" summaryFields={summaryFields} />;
}
