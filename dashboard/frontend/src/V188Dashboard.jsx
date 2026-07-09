import StageDashboard from './StageDashboard';

const endpoints = [["Shadow Governor Controller", "/api/v188/shadow-governor-controller"], ["V187 Baseline", "/api/v188/v187-baseline"], ["Candidate Input Snapshot", "/api/v188/candidate-input-snapshot"], ["Evidence Freshness Check", "/api/v188/evidence-freshness-check"], ["Contradiction Check", "/api/v188/contradiction-check"], ["Drift Check", "/api/v188/drift-check"], ["Settlement Ambiguity Check", "/api/v188/settlement-ambiguity-check"], ["Liquidity Slippage Check", "/api/v188/liquidity-slippage-check"], ["Risk Cap Check", "/api/v188/risk-cap-check"], ["Abstention First Policy", "/api/v188/abstention-first-policy"], ["Shadow Decision", "/api/v188/shadow-decision"], ["No Live Order Path Proof", "/api/v188/no-live-order-path-proof"], ["No Broker Payload Proof", "/api/v188/no-broker-payload-proof"], ["No Firewall Submit Access Proof", "/api/v188/no-firewall-submit-access-proof"], ["Readiness Governor", "/api/v188/readiness-governor"], ["Execution Lock", "/api/v188/execution-lock"], ["Mission State", "/api/v188/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Shadow Governor", "shadow_governor_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V188Dashboard() {
  return <StageDashboard title="Dummy V188 Autonomy Shadow Governor" endpoints={endpoints} missionKey="dummy_mission_state_report_v174" summaryFields={summaryFields} />;
}
