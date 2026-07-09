import StageDashboard from './StageDashboard';

const endpoints = [
  ['Risk Governor Controller', '/api/v72/risk-governor-controller'],
  ['V71 Baseline', '/api/v72/v71-baseline'],
  ['Max-Loss Check', '/api/v72/max-loss-check'],
  ['Exposure Check', '/api/v72/exposure-check'],
  ['Drift Check', '/api/v72/drift-check'],
  ['Slippage/Liquidity Review', '/api/v72/slippage-liquidity-review'],
  ['Fill Quality Review', '/api/v72/fill-quality-review'],
  ['Kill-Switch Verification', '/api/v72/kill-switch-verification'],
  ['Session-Lock Verification', '/api/v72/session-lock-verification'],
  ['Live-Submit/Caps Unchanged Proof', '/api/v72/live-submit-caps-unchanged-proof'],
  ['No-Repeat-Submit Proof', '/api/v72/no-repeat-submit-proof'],
  ['Readiness Governor V32', '/api/v72/readiness-governor'],
  ['Execution Lock V31', '/api/v72/execution-lock'],
  ['Mission State V72', '/api/v72/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V71 Baseline', 'v71_baseline_status'],
  ['Risk Governor', 'risk_governor_controller_status'],
  ['Max Loss', 'max_loss_check_status'],
  ['Exposure', 'exposure_check_status'],
  ['Kill-Switch', 'kill_switch_verification_status'],
  ['Session Lock', 'session_lock_verification_status'],
  ['Live-Submit/Caps', 'live_submit_caps_unchanged_proof_status'],
  ['Readiness', 'readiness_governor_v32_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v31_status'],
  ['Next Action', 'current_next_action']
];

export default function V72Dashboard() {
  return <StageDashboard title="Dummy V72 Post-Trade Risk Governor" endpoints={endpoints} missionKey="dummy_mission_state_report_v58" summaryFields={summaryFields} />;
}
