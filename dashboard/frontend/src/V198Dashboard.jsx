import StageDashboard from './StageDashboard';

const endpoints = [["Final Quorum Controller", "/api/v198/final-quorum-controller"], ["V197 Baseline", "/api/v198/v197-baseline"], ["Approval Quorum", "/api/v198/approval-quorum"], ["Config Caps Quorum", "/api/v198/config-caps-quorum"], ["Firewall Broker Quorum", "/api/v198/firewall-broker-quorum"], ["Mode Firewall Quorum", "/api/v198/mode-firewall-quorum"], ["Candidate Abstention Quorum", "/api/v198/candidate-abstention-quorum"], ["Risk Governor Quorum", "/api/v198/risk-governor-quorum"], ["Shadow Forensic Quorum", "/api/v198/shadow-forensic-quorum"], ["Kill Switch Quorum", "/api/v198/kill-switch-quorum"], ["Rollback Quorum", "/api/v198/rollback-quorum"], ["Idempotency Quorum", "/api/v198/idempotency-quorum"], ["Liquidity Slippage Quorum", "/api/v198/liquidity-slippage-quorum"], ["Limit Only No Market Quorum", "/api/v198/limit-only-no-market-quorum"], ["Reconcile Readiness Quorum", "/api/v198/reconcile-readiness-quorum"], ["Proof Target Selector", "/api/v198/proof-target-selector"], ["No Submit Proof", "/api/v198/no-submit-proof"], ["Readiness Governor", "/api/v198/readiness-governor"], ["Execution Lock", "/api/v198/execution-lock"], ["Mission State", "/api/v198/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Final Quorum", "final_quorum_controller_status"], ["Proof Target", "proof_target"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V198Dashboard() {
  return <StageDashboard title="Dummy V198 First Live-Proof Final Quorum" endpoints={endpoints} missionKey="dummy_mission_state_report_v184" summaryFields={summaryFields} />;
}
