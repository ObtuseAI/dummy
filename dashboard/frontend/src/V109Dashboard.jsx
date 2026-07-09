import StageDashboard from './StageDashboard';

const endpoints = [
  ['Abstention Governor Controller', '/api/v109/abstention-governor-controller'],
  ['V108 Baseline', '/api/v109/v108-baseline'],
  ['Abstention Rules', '/api/v109/abstention-rules'],
  ['Abstention Ledger', '/api/v109/abstention-ledger'],
  ['False Abstention Review', '/api/v109/false-abstention-review'],
  ['No Auto Trade Proof', '/api/v109/no-auto-trade-proof'],
  ['Readiness Governor', '/api/v109/readiness-governor'],
  ['Execution Lock', '/api/v109/execution-lock'],
  ['Mission State', '/api/v109/mission-state']
];

const summaryFields = [
  ['Mission', 'mission_state_verdict'],
  ['Abstention Governor', 'abstention_governor_status'],
  ['Autonomous Trading', 'autonomous_trading_enabled'],
  ['Rules Active', 'abstention_rules_count'],
  ['Next Action', 'current_next_action'],
  ['Blockers', 'current_blockers']
];

export default function V109Dashboard() {
  return <StageDashboard title='Dummy V109 Autonomous Abstention Governor' endpoints={endpoints} missionKey='dummy_mission_state_report_v95' summaryFields={summaryFields} />;
}
