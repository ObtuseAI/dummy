import StageDashboard from './StageDashboard';

const endpoints = [["Pilot Blocker Controller", "/api/v126/pilot-blocker-controller"], ["V125 Baseline", "/api/v126/v125-baseline"], ["Blocker Classifier", "/api/v126/blocker-classifier"], ["Pilot Approval Blocker", "/api/v126/pilot-approval-blocker"], ["Firewall Adapter Blocker", "/api/v126/firewall-adapter-blocker"], ["Live Submit Caps Blocker", "/api/v126/live-submit-caps-blocker"], ["Broker Private Access Blocker", "/api/v126/broker-private-access-blocker"], ["Repeat Scale Autonomy Blocker", "/api/v126/repeat-scale-autonomy-blocker"], ["Next Action Matrix", "/api/v126/next-action-matrix"], ["No Submit Proof", "/api/v126/no-submit-proof"], ["No Broker Contact Proof", "/api/v126/no-broker-contact-proof"], ["Readiness Governor", "/api/v126/readiness-governor"], ["Execution Lock", "/api/v126/execution-lock"], ["Mission State", "/api/v126/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Blocker Audit", "pilot_blocker_controller_status"], ["Next Action Matrix", "next_action_matrix_selection"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V126Dashboard() {
  return <StageDashboard title="Dummy V126 Production Pilot Blocker Closure V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v112" summaryFields={summaryFields} />;
}
