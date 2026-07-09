import StageDashboard from './StageDashboard';

const endpoints = [["Limited Autonomy Dryrun Controller", "/api/v183/limited-autonomy-dryrun-controller"], ["V182 Baseline", "/api/v183/v182-baseline"], ["Dry Run Only Policy", "/api/v183/dry-run-only-policy"], ["No Live Submit Path Proof", "/api/v183/no-live-submit-path-proof"], ["No Broker Payload Proof", "/api/v183/no-broker-payload-proof"], ["Candidate Simulation Loop", "/api/v183/candidate-simulation-loop"], ["Abstention First Decision Loop", "/api/v183/abstention-first-decision-loop"], ["Risk Stop Loop", "/api/v183/risk-stop-loop"], ["Hypothetical Order Scoring", "/api/v183/hypothetical-order-scoring"], ["Hypothetical Reconcile Schema", "/api/v183/hypothetical-reconcile-schema"], ["Autonomous Live Trading Disabled Proof", "/api/v183/autonomous-live-trading-disabled-proof"], ["Dryrun Cannot Call Firewall Submit Proof", "/api/v183/dryrun-cannot-call-firewall-submit-proof"], ["No Scale Proof", "/api/v183/no-scale-proof"], ["Readiness Governor", "/api/v183/readiness-governor"], ["Execution Lock", "/api/v183/execution-lock"], ["Mission State", "/api/v183/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry-Run Policy", "limited_autonomy_dryrun_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V183Dashboard() {
  return <StageDashboard title="Dummy V183 Limited Autonomy Dry-Run Policy" endpoints={endpoints} missionKey="dummy_mission_state_report_v169" summaryFields={summaryFields} />;
}
