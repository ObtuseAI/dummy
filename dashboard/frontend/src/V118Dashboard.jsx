import StageDashboard from './StageDashboard';

const endpoints = [["Production Dry Audit Controller", "/api/v118/production-dry-audit-controller"], ["V117 Baseline", "/api/v118/v117-baseline"], ["Dry Audit Approval Validator", "/api/v118/dry-audit-approval-validator"], ["Production Config Checklist", "/api/v118/production-config-checklist"], ["Firewall Checklist", "/api/v118/firewall-checklist"], ["Risk Checklist", "/api/v118/risk-checklist"], ["Abstention Checklist", "/api/v118/abstention-checklist"], ["Reconcile Checklist", "/api/v118/reconcile-checklist"], ["Dashboard Api Safety Checklist", "/api/v118/dashboard-api-safety-checklist"], ["No Broker Contact Proof", "/api/v118/no-broker-contact-proof"], ["No Order Proof", "/api/v118/no-order-proof"], ["Readiness Governor", "/api/v118/readiness-governor"], ["Execution Lock", "/api/v118/execution-lock"], ["Mission State", "/api/v118/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry Audit", "production_dry_audit_controller_status"], ["Broker Contacted", "broker_contacted"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V118Dashboard() {
  return <StageDashboard title="Dummy V118 Production Dry Audit" endpoints={endpoints} missionKey="dummy_mission_state_report_v104" summaryFields={summaryFields} />;
}
