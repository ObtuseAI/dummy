# DUMMY vNext Phase 4 versioned world models

Status: **COMPLETE_VALIDATED**

Phase 4 replaces the Phase 3 placeholder state bundle with an immutable,
content-addressed world-state contract. Every supported state is specific to
one forecast horizon or one sports league and game clock. Hydration consumes
only evidence that was already frozen by the decision clock; it performs no
network reads, backfills, imputations, or source arbitration.

This phase remains research-only. It changes neither the incumbent forecast
nor any order, weight, promotion decision, credential boundary, or capital
authority.

## Delivered state contract

`dummy/world_model` provides:

- 8 horizon-specific crypto schemas from quote through expiry clocks;
- league-valid pregame and live-clock schemas for MLB, NBA, NFL, NCAAF, NHL,
  and NCAAMB, excluding nonsensical league/clock combinations;
- explicit `FACT`, `DERIVED`, `HYPOTHESIS`, and `MISSING` layers;
- explicit `PRESENT`, `MISSING`, `STALE`, and `CONTRADICTED` value states;
- a required unit, uncertainty, lease, missing-data policy, transform version,
  causal evidence, and provenance chain for every schema value;
- calibration identity and mapping evidence for every probabilistic
  hypothesis;
- deterministic revision lineage and rejection of unlinked disagreement;
- blocking market-status and two-sided-book coherence checks;
- a content-derived snapshot identity that rejects independently supplied or
  tampered IDs;
- immutable mapping/sequence values and canonical serialization.

The canonical 52-schema catalog and content digests are stored in
`docs/VNEXT_PHASE4_WORLD_MODEL_SCHEMAS.json`.

## Fail-closed hydration

The initial migration marks the frozen two-sided market book and incumbent
probability/uncertainty as critical. Missing, contradicted, stale, unverified,
future-received, out-of-schema, wrong-unit, or wrong-layer critical values stop
issuance. Optional model fields are never guessed: the snapshot carries an
explicit missing status, maximum uncertainty, its configured response policy,
and the reason the value is unavailable.

Incoming revisions must form one causal supersession chain. Independent equal
observations may corroborate a value and retain all provenance. Independent
disagreement becomes a typed contradiction; a critical contradiction blocks
the snapshot, while an optional contradiction stays visible as unavailable
instead of being arbitrarily resolved.

The Phase 2 incumbent bridge now preserves its exact feature manifest and
calibration identity. Recognized crypto volatility and horizon fields are
copied only as derived state with inherited uncertainty and causal evidence.
Other feature values remain in the exact manifest; no undocumented
statistic-to-probability or feature-to-world-state mapping is invented.

## Organism integration

`issue_episode` resolves and freezes one Phase 4 snapshot before any agent is
invoked. Its snapshot ID is the episode `state_version`. Every market-prior,
specialist, contrarian, calibration, adversarial, shadow, and synthesizer
message must receive and propagate exactly that version. Missing or mixed
versions fail closed. The state never mutates during issuance, and later
settlement still attaches to the immutable issued artifact without rerunning
the agents.

The initial organism pilots remain BTC 15-minute direction and MLB pregame
winner. Schemas for the other horizons, leagues, and live clocks are ready for
typed adapters in later organisms, but schema availability is not evidence of
forecast quality.

## Ablation and regime-transfer evidence

`scripts/run_vnext_phase4_world_model_audit.py` accepts optional verified,
settled, unique-event-cluster evaluation cases and emits deterministic:

- field ablation Brier comparisons; and
- training-to-target regime Brier and log-loss comparisons.

Both require at least 30 distinct settled event clusters per field or transfer
pair by default. The current artifacts honestly report
`INSUFFICIENT_SETTLED_EVIDENCE` with zero cases:

- `docs/VNEXT_PHASE4_WORLD_STATE_ABLATION.json`
- `docs/VNEXT_PHASE4_REGIME_TRANSFER.json`

Those artifacts prove the reporting and no-claim gates exist; they do not prove
that any new world-state field improves forecasts or transfers across regimes.

## Evidence and non-claims

Focused Phase 4 contract, hydration, integration, and evaluation tests cover:

- schema routing for every supported horizon, league, and game clock;
- canonical snapshot replay and tamper rejection;
- future-evidence, stale-lease, revision-conflict, and missing-calibration
  failures;
- explicit uncertainty and provenance;
- one-version propagation across all seven organism roles;
- verified-settlement and event-cluster requirements for evaluation.

Validation completed on 2026-07-14:

- focused Phase 4 plus organism tests: **41 passed**;
- complete cross-vNext family: **127 passed**;
- complete autonomy family: **1,134 passed**;
- expanded firewall, secret, live-submit, and order-bypass family:
  **379 passed**;
- repository-wide Ruff and Python compilation: **passed**;
- full repository suite: **5,626 passed in 409.78 seconds**;
- deterministic artifact generation and `git diff --check`: **passed**.

Phase 4 demonstrates causal state architecture, not better forecast
performance, canary readiness, scale readiness, or capital readiness. The
Phase 0 baseline remains `NOT_READY`.
