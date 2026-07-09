import StageDashboard from './StageDashboard';

const endpoints = [
  ['Second Canary Controller', '/api/v81/second-canary-controller'],
  ['V80 Baseline', '/api/v81/v80-baseline'],
  ['Single Submit Guard', '/api/v81/single-submit-guard'],
  ['Repeat Approval Validator', '/api/v81/repeat-approval-validator'],
  ['Risk Threshold Validator', '/api/v81/risk-threshold-validator'],
  ['Livebrokerfirewall Submit Adapter', '/api/v81/livebrokerfirewall-submit-adapter'],
  ['Post Submit Auto Lock', '/api/v81/post-submit-auto-lock'],
  ['Readiness Governor', '/api/v81/readiness-governor'],
  ['Execution Lock', '/api/v81/execution-lock'],
  ['Mission State', '/api/v81/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Real Orders', 'real_live_orders_submitted_count'],
  ['Real Broker Contacted', 'real_broker_contacted'],
  ['Repeat Approval', 'repeat_approval_validator_status'],
  ['Auto-Lock', 'post_submit_auto_lock_status'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V81Dashboard() {
  return <StageDashboard title="Dummy V81 Second Tiny Live Limit-Order Canary" endpoints={endpoints} missionKey="dummy_mission_state_report_v67" summaryFields={summaryFields} />;
}
