import StageDashboard from './StageDashboard';

const endpoints = [["Shadow Forensic Controller", "/api/v189/shadow-forensic-controller"], ["V188 Baseline", "/api/v189/v188-baseline"], ["Shadow Decision Summary", "/api/v189/shadow-decision-summary"], ["Abstention Correctness Review", "/api/v189/abstention-correctness-review"], ["False Positive Trade Candidate Review", "/api/v189/false-positive-trade-candidate-review"], ["False Negative Abstention Review", "/api/v189/false-negative-abstention-review"], ["Risk Policy Violation Scan", "/api/v189/risk-policy-violation-scan"], ["Missing Evidence Scan", "/api/v189/missing-evidence-scan"], ["Stale Evidence Scan", "/api/v189/stale-evidence-scan"], ["Drift Lock Scan", "/api/v189/drift-lock-scan"], ["Liquidity Lock Scan", "/api/v189/liquidity-lock-scan"], ["Operator Escalation Quality", "/api/v189/operator-escalation-quality"], ["No Submit Proof", "/api/v189/no-submit-proof"], ["No Broker Contact Proof", "/api/v189/no-broker-contact-proof"], ["Readiness Governor", "/api/v189/readiness-governor"], ["Execution Lock", "/api/v189/execution-lock"], ["Mission State", "/api/v189/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Shadow Forensic", "shadow_forensic_controller_status"], ["Abstention Correctness", "abstention_correctness_review_status"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V189Dashboard() {
  return <StageDashboard title="Dummy V189 Shadow Decision Forensic Review" endpoints={endpoints} missionKey="dummy_mission_state_report_v175" summaryFields={summaryFields} />;
}
