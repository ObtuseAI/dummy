import StageDashboard from './StageDashboard';

const endpoints = [["Final Authority Readiness Console", "/api/v276/final-authority-readiness-console"], ["V275 Baseline", "/api/v276/v275-baseline"], ["Authority Readiness Matrix", "/api/v276/authority-readiness-matrix"], ["Ui Flags", "/api/v276/ui-flags"], ["No Submit Proof", "/api/v276/no-submit-proof"], ["No Broker Contact Proof", "/api/v276/no-broker-contact-proof"], ["Readiness Governor", "/api/v276/readiness-governor"], ["Execution Lock", "/api/v276/execution-lock"], ["Mission State", "/api/v276/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Console", "final_authority_readiness_console_controller_status"], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action", "current_next_action"]];

export default function V276Dashboard() {
  return <StageDashboard title="Dummy V276 Final Authority Readiness Console" endpoints={endpoints} missionKey="dummy_mission_state_report_v276" summaryFields={summaryFields} />;
}
