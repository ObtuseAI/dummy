import StageDashboard from './StageDashboard';

const endpoints = [
  ['Approval Packet Validator', '/api/v66/approval-packet-validator'],
  ['V65 Baseline', '/api/v66/v65-baseline'],
  ['Exact Phrase Policy', '/api/v66/exact-phrase-policy'],
  ['Approval Metadata Validator', '/api/v66/approval-metadata-validator'],
  ['Live-Submit Config Readonly Checker', '/api/v66/live-submit-config-readonly-checker'],
  ['Caps Config Readonly Checker', '/api/v66/caps-config-readonly-checker'],
  ['No-Enable/No-Modify Proof', '/api/v66/no-enable-no-modify-proof'],
  ['Readiness Governor V26', '/api/v66/readiness-governor'],
  ['Execution Lock V25', '/api/v66/execution-lock'],
  ['Mission State V66', '/api/v66/mission-state'],
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V65 Baseline', 'v65_baseline_status'],
  ['Approval Validator', 'approval_packet_validator_status'],
  ['Live-Submit Readonly', 'live_submit_config_readonly_checker_status'],
  ['Caps Readonly', 'caps_config_readonly_checker_status'],
  ['No-Enable/No-Modify', 'no_enable_no_modify_proof_status'],
  ['Readiness', 'readiness_governor_v26_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v25_status'],
  ['Next Action', 'current_next_action'],
];

export default function V66Dashboard() {
  return <StageDashboard title="Dummy V66 Live-Canary Approval Packet Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v52" summaryFields={summaryFields} />;
}
