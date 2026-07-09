import StageDashboard from './StageDashboard';

const endpoints = [["Operator Activation Packet Controller", "/api/v215/operator-activation-packet-controller"], ["V214 Baseline", "/api/v215/v214-baseline"], ["Operator Checklist", "/api/v215/operator-checklist"], ["First Live Proof Command Sequence", "/api/v215/first-live-proof-command-sequence"], ["Reconcile Command Sequence", "/api/v215/reconcile-command-sequence"], ["Forensic Command Sequence", "/api/v215/forensic-command-sequence"], ["No Approval File Write Proof", "/api/v215/no-approval-file-write-proof"], ["No Config Write Proof", "/api/v215/no-config-write-proof"], ["No Submit Proof", "/api/v215/no-submit-proof"], ["No Broker Contact Proof", "/api/v215/no-broker-contact-proof"], ["Readiness Governor", "/api/v215/readiness-governor"], ["Execution Lock", "/api/v215/execution-lock"], ["Mission State", "/api/v215/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Activation Packet", "operator_activation_packet_controller_status"], ["Approval Files Written", "approval_files_written"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V215Dashboard() {
  return <StageDashboard title="Dummy V215 Operator Activation Packet Readonly Completion Actions" endpoints={endpoints} missionKey="dummy_mission_state_report_v201" summaryFields={summaryFields} />;
}
