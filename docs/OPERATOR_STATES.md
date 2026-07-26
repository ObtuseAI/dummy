# Dummy operator-state contract

This vocabulary is shared by the canonical dashboard, readiness reports, and
operator documentation. Unknown, missing, malformed, expired, or contradictory
evidence always collapses toward `LOCKED`; display language never grants
authority.

| Display state | Exact meaning | May submit? |
|---|---|---|
| `LOCKED` | One or more firewall-authority predicates fail, evidence is invalid, the kill switch is active, or the state cannot be proven. | No |
| `ARMED / NO SESSION` | Firewall authority is locally valid, but no unexpired `LIVE` session satisfies the separate session contract. | No |
| `LIVE` | Firewall authority and the unexpired `LIVE` session both pass, the kill gate is clear, and the proposed order still passes every per-order caps/risk/EV check. | Only through the canonical firewall |
| `PENDING CANCEL AND RECONCILE` | Stop was requested and open-order state has not yet been proven flat by a separately authorized cancellation/reconciliation coordinator. | No |

`LIVE` is a narrow technical state, not a profitability, calibration, promotion,
or capital-readiness claim. A later gate may only reduce authority. It cannot
expand a prior decision.

The dashboard is a loopback-only, GET-only observer. It may display these
states but cannot create a session, write authority files, change caps, start or
stop the scheduler, cancel an order, or submit one.

For the current operator-only procedure, see
[LIVE_DEPLOY_RUNBOOK.md](LIVE_DEPLOY_RUNBOOK.md). For the evidence gate that
must be satisfied before any separate authority review, see
[ELITE_READINESS_IMPLEMENTATION_2026-07-26.md](ELITE_READINESS_IMPLEMENTATION_2026-07-26.md).
