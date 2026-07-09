import StageDashboard from './StageDashboard';

const endpoints = [
  ['Config Tieout Controller', '/api/v75/config-tieout-controller'],
  ['V74 Baseline', '/api/v75/v74-baseline'],
  ['Live Submit Readonly Checker', '/api/v75/live-submit-readonly-checker'],
  ['Caps Readonly Checker', '/api/v75/caps-readonly-checker'],
  ['Exact Approval File Validator', '/api/v75/exact-approval-file-validator'],
  ['Expiry Scope Max One Order Validator', '/api/v75/expiry-scope-max-one-order-validator'],
  ['No Enable Live Submit Proof', '/api/v75/no-enable-live-submit-proof'],
  ['No Caps Modification Proof', '/api/v75/no-caps-modification-proof'],
  ['Readiness Governor', '/api/v75/readiness-governor'],
  ['Execution Lock', '/api/v75/execution-lock'],
  ['Mission State', '/api/v75/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Exact Approval', 'exact_approval_file_validator_status'],
  ['No-Enable Live-Submit', 'no_enable_live_submit_proof_status'],
  ['No-Caps-Mod', 'no_caps_modification_proof_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V75Dashboard() {
  return <StageDashboard title="Dummy V75 Operator Live Config/Caps/Approval Tieout" endpoints={endpoints} missionKey="dummy_mission_state_report_v61" summaryFields={summaryFields} />;
}
