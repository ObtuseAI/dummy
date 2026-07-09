import StageDashboard from './StageDashboard';

const endpoints = [
  ['Final Tieout Controller', '/api/v69/final-tieout-controller'],
  ['V68 Baseline', '/api/v69/v68-baseline'],
  ['Dry/Shadow Schema Validator', '/api/v69/dry-shadow-schema-validator'],
  ['Candidate Tieout Validator', '/api/v69/candidate-tieout-validator'],
  ['LiveBrokerFirewall-Only Proof', '/api/v69/livebrokerfirewall-only-proof'],
  ['No-Direct-Broker-Bypass Proof', '/api/v69/no-direct-broker-bypass-proof'],
  ['No-Submit/No-Cancel Proof', '/api/v69/no-submit-no-cancel-proof'],
  ['Kill-Switch Readiness', '/api/v69/kill-switch-readiness-proof'],
  ['Rollback Readiness', '/api/v69/rollback-readiness-proof'],
  ['Idempotency Readiness', '/api/v69/idempotency-readiness-proof'],
  ['Caps-Readonly Proof', '/api/v69/caps-readonly-proof'],
  ['Live-Submit Status Proof', '/api/v69/live-submit-status-proof'],
  ['Readiness Governor V29', '/api/v69/readiness-governor'],
  ['Execution Lock V28', '/api/v69/execution-lock'],
  ['Mission State V69', '/api/v69/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V68 Baseline', 'v68_baseline_status'],
  ['Tieout Controller', 'final_tieout_controller_status'],
  ['No-Submit/No-Cancel', 'no_submit_no_cancel_proof_status'],
  ['Firewall-Only', 'livebrokerfirewall_only_proof_status'],
  ['No-Direct-Bypass', 'no_direct_broker_bypass_proof_status'],
  ['Live-Submit Status', 'live_submit_status_proof_status'],
  ['Readiness', 'readiness_governor_v29_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v28_status'],
  ['Next Action', 'current_next_action']
];

export default function V69Dashboard() {
  return <StageDashboard title="Dummy V69 Final Dry/Shadow/Firewall Tieout" endpoints={endpoints} missionKey="dummy_mission_state_report_v55" summaryFields={summaryFields} />;
}
