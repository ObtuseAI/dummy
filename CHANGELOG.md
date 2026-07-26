# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Rights-reviewed, provider-neutral BTC/ETH/SOL Market Observer MCP with
  content-addressed closed-candle evidence, indicators, candlestick patterns,
  rate/circuit/single-run guards, and a GET-only dashboard chart surface.
- Locally vendored TradingView Lightweight Charts 5.2.0 renderer with pinned
  hashes, license/notice, package-data inclusion, and no TradingView data or
  account integration.
- Cooperative ledger maintenance lease, verified off-volume online backups,
  restore drills, gated vacuum/retention/prune tools, and a no-shell job
  supervisor with exact exit receipts.
- Out-of-band settlement-grading worker and atomic grading support.
- Hash-chained recursive-research control plane with preregistration,
  deterministic negative controls, explicit resource budgets, zero inherited
  environment, and no automatic promotion.
- Fail-closed elite-readiness validator, authority-state matrix, dependency
  license gate, vulnerability-audit workflow, and frozen `uv.lock`.
- Opt-in, allowlisted critical HTTPS alert delivery plus content-aware
  retention and research-stall watchdog checks.
- Shared operator-state vocabulary and current-document index.
- Coverage gate in the `tests` CI job: `pytest-cov` now reports line coverage
  across the main packages (`--cov-report=term`) and enforces a `--cov-fail-under`
  floor.
- `pytest-cov` added to the `dev` optional-dependency group.
- `CHANGELOG.md` following the Keep a Changelog format.

### Changed
- The canonical operator board is loopback-only, GET-only, responsive, and
  reads persisted evidence without broker, provider, scheduler, authority,
  risk, or capital mutations.
- Live-firewall EV is independently recomputed with conservative uncertainty,
  fees, caps, and evidence-gated adverse-selection haircuts; per-candidate
  sizing uses uncertainty-adjusted Kelly under existing ceilings.
- Fused calibration can affect a decision only through exact, content-bound
  settled-evidence promotion; no scope is promoted by this release.
- Macro/equity crypto evidence abstains on physics-incompatible 15m/1h
  horizons, debate output is explicitly record-only, and fee schedules warn
  before their fail-closed staleness cliff.
- CI now installs and runs the exact frozen environment with `uv`.

### Removed
- Android operator app, Node/React client, tailnet listener, PySide Tote
  renderer, and the duplicate legacy FastAPI dashboard.
- Dormant live-order route alternatives and the unused V1 forecast engine.
- Historical `archive/` generators/routes, all `predator_mesh/vNN` source
  packages, generated adapter shells, constant-abstention strategies, and
  their duplicate historical tests. Preserved contracts live in stable,
  hash-pinned registries; historical source remains in Git.

### Security
- Research subprocesses inherit no parent environment variables and cannot
  access execution, credentials, network, capital, or promotion authority.
- Dashboard peer/Host validation, restrictive browser headers, public-source
  rights metadata, exact provider-host allowlists, redacted alert receipts,
  and fail-closed stale/malformed evidence handling are enforced by tests.

## [0.1.0] - 2026-07-16

Initial published history, reconstructed from merged pull requests (newest first).

### Added
- Add Intelligence Research Lab, crypto TA foundry, and multi-cohort autoresearch (#94)
- docs: architecture diagram + pre-commit tooling (#93)
- Add proprietary LICENSE and SECURITY.md (#92)
- build(deps): bump esbuild and vite in /dashboard/frontend (#90)
- Add exact-cohort real-ledger autoresearch (#89)
- Add recursive evidence-driven performance repair (#88)
- docs(vnext): complete master plan audit (#87)
- feat(vnext): add claim and promotion review (#86)
- feat(vnext): add observatory arenas and homeostasis (#85)
- feat(vnext): add causal memory and bounded evolution (#84)
- vNext Phase 5: contraction-only metacognition (#83)
- Build vNext Phase 4 world models (#82)
- vNext Phase 3: deterministic forecast organisms (#81)
- vNext Phase 2: deterministic agent control plane (#80)
- vNext Phase 0/1: constitutional and causal foundation (#79)
- Clean Ruff backlog and establish vNext foundation (#78)
- Complete evidence governance and live sports models (#77)
- Complete live sports evidence hardening and verified ledger retention (#76)
- docs: CF1/CF2 done in takeover report (#75)
- feat: consume power_divergence as buy-low evidence (CF1) (#74)
- feat: re-warm Massey/Colley ratings on a TTL cadence (CF2) (#73)
- docs: Phenon integration shipped + takeover report (#72)
- feat(phenon): in-house Massey + Colley rating sources (WS-A1b) (#71)
- fix: consensus_margin per-source point-margin scaling (Critical) (#70)
- feat(phenon): power-ratings challenger ladder + divergence flag (WS-A2) (#69)
- feat(phenon): loss-deconstruction evolution engine + narration (WS-B) (#68)
- feat(phenon): power-ratings fetch + consensus core (WS-A1) (#67)
- docs: L1 market-state routing (Phenon manifold) documentation (WS-C) (#66)
- docs: Phenon Harness integration — design spec + implementation plan (#65)
- feat: council dashboard panel + docs sweep (WS-13) (#64)
- feat: crypto CLV completion — DVOL book close semantics + e2e grading (WS-12) (#63)
- feat: NFL/NCAAF outdoor weather totals adjustment (WS-10) (#62)
- feat: propose-then-promote parameter tuner — artifact-only, walk-forward (WS-9) (#61)
- feat: situational engine — rest/playoff/suspension/roster-drift (WS-7) (#60)
- feat: player availability + rookie + mismatch layer across engines (WS-6) (#59)
- feat: NCAAF college margin kernel + NCAAMB pace model (WS-4) (#58)
- feat: NHL bivariate-Poisson engine — OT/SO, puck line, goalie layer (WS-3) (#57)
- feat: NBA pace × efficiency engine — heteroskedastic, rest-aware (WS-2) (#56)
- feat: MLB Phase 2 — park factors, live base-out RE, TTO, rest/travel (WS-11) (#55)
- feat: CLV grading + trust surface (WS-8) (#54)
- feat: 3x3 conviction lattice + coherence engine (WS-5) (#53)
- feat: boxscore stat pipeline (WS-1) (#52)
- WS-19: crypto fast lane + liquidity-bucketed edge floors (#51)
- WS-18: reliability calibration wrappers (isotonic recalibration challengers) (#50)
- WS-17: BTC-to-alt lead-lag challenger (spot only, no perpetuals) (#49)
- WS-16: vol triangulation + VRP regime + settlement-proximity guard (#48)
- WS-14: promotion protocol + readiness report (the ceiling remover) (#47)
- WS-15: horizon taxonomy + per-scope trust keying (#46)
- Build-out plan Part II — floor raisers, ceiling removers, readiness accelerators (WS-14…WS-19) (#45)
- Council build-out master plan — full design handoff (every sport, every layer) (#44)

[Unreleased]: https://github.com/ObtuseAI/dummy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ObtuseAI/dummy/releases/tag/v0.1.0
