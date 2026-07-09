import StageDashboard from './StageDashboard';

const endpoints = [["Autonomy Policy Controller", "/api/v116/autonomy-policy-controller"], ["V115 Baseline", "/api/v116/v115-baseline"], ["Trade Eligibility Policy", "/api/v116/trade-eligibility-policy"], ["Abstention Policy", "/api/v116/abstention-policy"], ["Lock Escalate Policy", "/api/v116/lock-escalate-policy"], ["Approval Required Policy", "/api/v116/approval-required-policy"], ["Policy State Machine", "/api/v116/policy-state-machine"], ["No Auto Order Proof", "/api/v116/no-auto-order-proof"], ["No Auto Scale Proof", "/api/v116/no-auto-scale-proof"], ["No Live Submit Caps Change Proof", "/api/v116/no-live-submit-caps-change-proof"], ["Readiness Governor", "/api/v116/readiness-governor"], ["Execution Lock", "/api/v116/execution-lock"], ["Mission State", "/api/v116/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Autonomy Policy", "autonomy_policy_controller_status"], ["Default State", "default_policy_state"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V116Dashboard() {
  return <StageDashboard title="Dummy V116 Autonomous Trade/Abstain/Lock Policy" endpoints={endpoints} missionKey="dummy_mission_state_report_v102" summaryFields={summaryFields} />;
}
