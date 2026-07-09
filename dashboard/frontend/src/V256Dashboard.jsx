import StageDashboard from './StageDashboard';

const endpoints = [["Single Command Operator Pipeline Controller", "/api/v256/single-command-operator-pipeline-controller"], ["V255 Baseline", "/api/v256/v255-baseline"], ["Pipeline Stages", "/api/v256/pipeline-stages"], ["Dry Default Proof", "/api/v256/dry-default-proof"], ["No Firewall Submit Proof", "/api/v256/no-firewall-submit-proof"], ["No Broker Payload Proof", "/api/v256/no-broker-payload-proof"], ["No Approval File Write Proof", "/api/v256/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v256/no-runtime-approvals-proof"], ["No Config Caps Mutation Proof", "/api/v256/no-config-caps-mutation-proof"], ["No Broker Contact Proof", "/api/v256/no-broker-contact-proof"], ["Readiness Governor", "/api/v256/readiness-governor"], ["Execution Lock", "/api/v256/execution-lock"], ["Mission State", "/api/v256/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Single-Command Pipeline", "single_command_operator_pipeline_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V256Dashboard() {
  return <StageDashboard title="Dummy V256 Single Command Operator Pipeline Dry Default" endpoints={endpoints} missionKey="dummy_mission_state_report_v242" summaryFields={summaryFields} />;
}
