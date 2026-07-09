import StageDashboard from './StageDashboard';

const endpoints = [["Completion Baseline Controller", "/api/v205/completion-baseline-controller"], ["V204 Baseline", "/api/v205/v204-baseline"], ["Canonical Blocker List", "/api/v205/canonical-blocker-list"], ["Redundant Gate Detection", "/api/v205/redundant-gate-detection"], ["Next Action Compression", "/api/v205/next-action-compression"], ["Completion Percentage Estimate", "/api/v205/completion-percentage-estimate"], ["No Submit Proof", "/api/v205/no-submit-proof"], ["No Broker Contact Proof", "/api/v205/no-broker-contact-proof"], ["No Approval File Write Proof", "/api/v205/no-approval-file-write-proof"], ["Readiness Governor", "/api/v205/readiness-governor"], ["Execution Lock", "/api/v205/execution-lock"], ["Mission State", "/api/v205/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Baseline Dedup", "completion_baseline_controller_status"], ["Remaining Blockers", "remaining_blocker_count"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V205Dashboard() {
  return <StageDashboard title="Dummy V205 Completion Accelerator Baseline" endpoints={endpoints} missionKey="dummy_mission_state_report_v191" summaryFields={summaryFields} />;
}
