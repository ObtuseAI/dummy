import StageDashboard from './StageDashboard';

const endpoints = [["Readiness Quorum Controller", "/api/v160/readiness-quorum-controller"], ["V159 Baseline", "/api/v160/v159-baseline"], ["Approval Linter Quorum", "/api/v160/approval-linter-quorum"], ["Live Submit Caps Quorum", "/api/v160/live-submit-caps-quorum"], ["Firewall Adapter Quorum", "/api/v160/firewall-adapter-quorum"], ["Broker Readonly Quorum", "/api/v160/broker-readonly-quorum"], ["Mode Firewall Quorum", "/api/v160/mode-firewall-quorum"], ["Candidate Abstention Quorum", "/api/v160/candidate-abstention-quorum"], ["Risk Governor Quorum", "/api/v160/risk-governor-quorum"], ["Kill Switch Quorum", "/api/v160/kill-switch-quorum"], ["Rollback Quorum", "/api/v160/rollback-quorum"], ["Idempotency Quorum", "/api/v160/idempotency-quorum"], ["Liquidity Slippage Quorum", "/api/v160/liquidity-slippage-quorum"], ["Limit Only No Market Quorum", "/api/v160/limit-only-no-market-quorum"], ["Reconcile Readiness Quorum", "/api/v160/reconcile-readiness-quorum"], ["No Submit Proof", "/api/v160/no-submit-proof"], ["Readiness Governor", "/api/v160/readiness-governor"], ["Execution Lock", "/api/v160/execution-lock"], ["Mission State", "/api/v160/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Readiness Quorum", "readiness_quorum_controller_status"], ["Quorum Ready", "quorum_ready"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V160Dashboard() {
  return <StageDashboard title="Dummy V160 Final Real Pilot Readiness Quorum" endpoints={endpoints} missionKey="dummy_mission_state_report_v146" summaryFields={summaryFields} />;
}
