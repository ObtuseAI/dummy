import StageDashboard from './StageDashboard';

const endpoints = [
  ['Broker Readonly Preflight Controller', '/api/v67/broker-readonly-preflight-controller'],
  ['V66 Baseline', '/api/v67/v66-baseline'],
  ['Secret Redaction Scanner', '/api/v67/secret-redaction-scanner'],
  ['Private Data Access Denial Proof', '/api/v67/private-data-access-denial-proof'],
  ['Broker Readonly Approval Validator', '/api/v67/broker-readonly-approval-validator'],
  ['Safe Connection Shape', '/api/v67/safe-connection-shape'],
  ['Account/Balance/Position Access Lock', '/api/v67/account-balance-position-access-lock'],
  ['Readiness Governor V27', '/api/v67/readiness-governor'],
  ['Execution Lock V26', '/api/v67/execution-lock'],
  ['Mission State V67', '/api/v67/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['V66 Baseline', 'v66_baseline_status'],
  ['Preflight', 'broker_readonly_preflight_controller_status'],
  ['Secret Redaction', 'secret_redaction_scanner_status'],
  ['Private Access Denial', 'private_data_access_denial_proof_status'],
  ['Broker RO Approval', 'broker_readonly_approval_validator_status'],
  ['Account Lock', 'account_balance_position_access_lock_status'],
  ['Readiness', 'readiness_governor_v27_status'],
  ['Execution Lock', 'execution_lock_deep_recheck_v26_status'],
  ['Next Action', 'current_next_action']
];

export default function V67Dashboard() {
  return <StageDashboard title="Dummy V67 Broker Read-Only Preflight" endpoints={endpoints} missionKey="dummy_mission_state_report_v53" summaryFields={summaryFields} />;
}
