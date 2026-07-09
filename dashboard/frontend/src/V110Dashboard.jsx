import StageDashboard from './StageDashboard';

const endpoints = [
  ['Production Readiness Controller', '/api/v110/production-readiness-controller'],
  ['V109 Baseline', '/api/v110/v109-baseline'],
  ['Campaign Evidence Review', '/api/v110/campaign-evidence-review'],
  ['Risk Policy Review', '/api/v110/risk-policy-review'],
  ['Abstention Policy Review', '/api/v110/abstention-policy-review'],
  ['Broker Firewall Readiness Review', '/api/v110/broker-firewall-readiness-review'],
  ['Live Submit Caps Control Review', '/api/v110/live-submit-caps-control-review'],
  ['Reconcile Readiness Review', '/api/v110/reconcile-readiness-review'],
  ['Audit Ledger Readiness', '/api/v110/audit-ledger-readiness'],
  ['Production Eligibility Status', '/api/v110/production-eligibility-status'],
  ['No Production Enable Proof', '/api/v110/no-production-enable-proof'],
  ['Readiness Governor', '/api/v110/readiness-governor'],
  ['Execution Lock', '/api/v110/execution-lock'],
  ['Mission State', '/api/v110/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Readiness Audit', 'production_readiness_controller_status'],
  ['Eligibility', 'production_eligibility_status'],
  ['Production Enabled', 'production_enabled'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V110Dashboard() {
  return <StageDashboard title='Dummy V110 Production Readiness Audit' endpoints={endpoints} missionKey='dummy_mission_state_report_v96' summaryFields={summaryFields} />;
}
