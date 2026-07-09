import StageDashboard from './StageDashboard';

const endpoints = [
  ['Scale Approval Controller', '/api/v107/scale-approval-controller'],
  ['V106 Baseline', '/api/v107/v106-baseline'],
  ['Scale Phrase Validator', '/api/v107/scale-phrase-validator'],
  ['Scale Scope Expiration Operator Checks', '/api/v107/scale-scope-expiration-operator-checks'],
  ['Campaign Evidence Prerequisite', '/api/v107/campaign-evidence-prerequisite'],
  ['Risk Prerequisite', '/api/v107/risk-prerequisite'],
  ['No Caps Modification Proof', '/api/v107/no-caps-modification-proof'],
  ['No Order Proof', '/api/v107/no-order-proof'],
  ['Readiness Governor', '/api/v107/readiness-governor'],
  ['Execution Lock', '/api/v107/execution-lock'],
  ['Mission State', '/api/v107/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Scale Approval', 'scale_approval_controller_status'],
  ['Scale Applied', 'scale_applied'],
  ['Caps Changed', 'caps_changed'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V107Dashboard() {
  return <StageDashboard title='Dummy V107 Scale Step 1 Approval Validator' endpoints={endpoints} missionKey='dummy_mission_state_report_v93' summaryFields={summaryFields} />;
}
