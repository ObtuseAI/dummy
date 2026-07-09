import StageDashboard from './StageDashboard';

const endpoints = [["Candidate Preflight Controller", "/api/v139/candidate-preflight-controller"], ["V138 Baseline", "/api/v139/v138-baseline"], ["Limit Only Candidate Refresh", "/api/v139/limit-only-candidate-refresh"], ["No Market Order Validator", "/api/v139/no-market-order-validator"], ["Liquidity Slippage Validator", "/api/v139/liquidity-slippage-validator"], ["Stale Evidence Check", "/api/v139/stale-evidence-check"], ["Contradiction Check", "/api/v139/contradiction-check"], ["Drift Check", "/api/v139/drift-check"], ["Settlement Ambiguity Check", "/api/v139/settlement-ambiguity-check"], ["Risk Cap Check", "/api/v139/risk-cap-check"], ["Abstention Decision", "/api/v139/abstention-decision"], ["No Submit Proof", "/api/v139/no-submit-proof"], ["Readiness Governor", "/api/v139/readiness-governor"], ["Execution Lock", "/api/v139/execution-lock"], ["Mission State", "/api/v139/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Candidate Preflight", "candidate_preflight_controller_status"], ["Abstention", "abstention_decision"], ["Submit Enabled", "submit_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V139Dashboard() {
  return <StageDashboard title="Dummy V139 Candidate Refresh & Abstention Preflight" endpoints={endpoints} missionKey="dummy_mission_state_report_v125" summaryFields={summaryFields} />;
}
