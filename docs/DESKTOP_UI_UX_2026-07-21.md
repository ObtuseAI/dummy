# DUMMY Desktop UI/UX Readiness Pass — 2026-07-21

## Outcome

The canonical desktop launcher (`desktop/launch_dummy.py`) opens the local
operator board in a chromeless Edge/Chrome app window. This pass therefore
targeted the served board in `autonomy/dashboard_ui.py` and left order
submission, risk limits, promotion gates, and live authorization unchanged.

The board is now outcome-first. It answers these questions in order:

1. Does the engine have live execution authority?
2. Is the engine and its evidence healthy/fresh?
3. Is paper execution actually profitable?
4. Has any strategy cleared promotion?
5. What do forecast-quality diagnostics say?

## Material improvements

- Added a persistent execution-authority bar. `SHADOW`, expired/missing live
  authorization, engine health, and stale evidence are visible on every route.
- Removed ambiguous `live` freshness language from the sidebar. It now says
  `snapshot` and separately displays the engine mode.
- Put realized P&L, ROI on cost, profit factor, win rate, and drawdown ahead of
  forecast hit rate and Brier diagnostics.
- Added a plain-language profitability verdict. High forecast accuracy is
  explicitly labeled diagnostic and not a substitute for realized returns.
- Added a dedicated deployment-readiness section and direct readiness action.
- Restricted prediction navigation to Crypto and Sports. Weather and
  Commodities are retained only as contextual input data and cannot appear as
  prediction or execution scopes.
- Added an evidence-backed crypto horizon panel to BTC, ETH, and SOL. It shows
  current listed targets, open diagnostic paper decisions, and tracked history
  separately for hourly, daily, weekly, and 15-minute markets. Normal
  positions remain EV/risk gated, and the panel explicitly says it has no
  broker contact.
- Added a today-first betting guide to every supported sports league (MLB,
  WNBA, NFL, NBA, NCAAF, NCAAMB, and NHL). Each guide shows every listed event,
  market-category tabs, unique-event counts, and rankings by absolute
  model-to-market gap.
- Made each matchup expandable with the recommended side, side-normalized
  model and market probabilities, gap, and confidence tier. `All markets`
  opens the complete cross-category board; a selected category now constrains
  the matchup list, ranking, counts, and expanded rows to that category.
- Preserved each league's selected category across live-data re-renders, added
  Home/End and arrow-key tab navigation, and automatically keeps the active tab
  visible in the compact horizontal strip.
- Made player props identifiable at a glance. Live-cycle rows carry the full
  player name and threshold from the market title; title-less ledger/snapshot
  fallback names the player's team rather than emitting an anonymous `hits`,
  `outs`, or `strikeouts` row.
- Added honest next-slate previews and empty states. Future games are never
  relabeled as today's games, and the guide refreshes when a new board artifact
  arrives.
- Added refresh and keyboard jump controls to every page header.
- Added a skip link, navigation labels, current-page semantics, dialog/listbox
  semantics, tab semantics, expanded-state semantics, and screen-reader-safe
  split-flap values.
- Added honest loading/degraded states. Partial API failure preserves the last
  good snapshot and says how many sources failed.
- Reworked the 1024 px layout so exposure/P&L stays beside bankroll before the
  ROI gauge; added a clean 72 px navigation rail below 920 px.
- Reduced decorative noise (static brand rim, weaker scanline/ambient field)
  while preserving the totalizator identity and reduced-motion behavior.
- Added an inline SVG favicon, eliminating the prior browser 404.
- Upgraded the bottom-left color controls into complete saved application
  themes. Emerald, amber, cyan, and violet now change the canvas, sidebar,
  cards, panels, borders, text hierarchy, glow, and accent together while
  retaining stable green/red outcome semantics. Choices remain available on
  the compact navigation rail and persist across reloads.
- Added a searchable `Glossary & how Dummy works` route to the sidebar and
  command palette. It explains the six-stage operating flow and 32 terms
  spanning forecasts, evidence, execution, risk, operating modes, and
  data-only inputs.
- Bounded the settled table to the 100 most recent rows and each category to
  the top 75 by edge, always showing the full total.
- Lazy-rendered inactive game-day and market-category panels. On the MLB route,
  the accessibility snapshot fell from roughly 23,000 referenced nodes to
  roughly 3,800 while category counts and on-demand access remained intact.
- Reworded open picks as open forecasts/model shortlist and marked them as
  forecast gaps, not orders.

## Verification

- `python -m py_compile autonomy/dashboard_ui.py autonomy/dashboard.py` — pass
- `git diff --check -- autonomy/dashboard_ui.py tests/test_dashboard_ui_contract.py` — pass
- Affected policy, forecasting, execution, board, sports-guide, firewall, and
  analytics pytest set — **154 passed**
- `python -m compileall -q autonomy forecasting live_firewall` — pass
- Chromium console after MLB, WNBA, NBA, and compact-guide flows —
  **0 errors, 0 warnings**
- Keyboard flow: `Ctrl+K` → type `MLB` → `Enter` — pass
- Rendered at 1500×950, 1024×768, and 900×800 — pass
- Current-board flow: MLB showed 15 events and more than 1,400 priced markets;
  category selection and click-through produced an 80-row full matchup table.
- Future/empty flow: WNBA truthfully showed zero events today plus a six-event
  next-slate preview; NBA truthfully showed no listed slate.
- Compact 720×900 flow — no page-level horizontal overflow; ranked rows retain
  rank, matchup, category, market count, side, and gap.
- Current crypto-twin browser evidence showed BTC, ETH, and SOL each actively
  tracking listed hourly, daily, weekly, and 15-minute targets.
- Scheduled cycle `paper-20260721T165902-bd3ecfb3` completed `CYCLE_OK` with
  the persisted 9-scope required contract (3 assets × hourly/daily/weekly), no
  reported errors, and no live or capital authority.
- Theme acceptance: all four themes changed independent background, panel,
  border, text, and accent variables; Cyan persisted across a full reload.
- Glossary acceptance: sidebar and command routes worked; searching `Brier`
  reduced the page from 32 terms to the two relevant definitions.
- Current-change regression slice — **128 passed** across crypto twin,
  quarantine, adaptive bars, autonomy pipeline, target policy, live firewall,
  dashboard, launcher, and scope analytics.
- Sports-guide repair focused slice — **40 passed** across board labels,
  dashboard UI contracts, scope analytics, and telemetry.
- Complete affected dashboard/sports/desktop regression pass — **259 passed**.
- Browser acceptance: selecting `Prop · Hits` reduced MLB from 1,580 markets to
  112 hit markets across 14 matchups; the opened DET–CHC matchup contained six
  rows, all categorized `Prop · Hits`, and all six named the player. Selection
  survived a forced re-render, arrow-key navigation changed both tab and panel,
  and the browser console remained at 0 errors / 0 warnings.
- League-state audit: WNBA, NFL, and NCAAF rendered honest next-slate previews;
  NBA, NCAAMB, and NHL rendered honest empty states. The single-event NFL
  preview uses correct singular grammar.
- Compact acceptance at 600 px: no page-level horizontal overflow, the category
  strip scrolls, the active category is automatically revealed, and ranked
  rows retain matchup, named prop, side, and gap.
- Live order controls, authorization files, capital limits, and promotion logic
  were not modified.

## Render evidence

- `output/playwright/dummy-ui-final/overview-desktop.png`
- `output/playwright/dummy-ui-final/overview-compact.png`
- `output/playwright/dummy-ui-final/scope-mlb-desktop.png`
- `output/playwright/final-verification/mlb-expanded-desktop.png`
- `output/playwright/final-verification/wnba-next-slate-desktop.png`
- `output/playwright/final-verification/nba-empty-desktop.png`
- `output/playwright/final-verification/mlb-compact-fixed.png`
- `output/playwright/crypto-theme-glossary/btc-horizon-operation.png`
- `output/playwright/crypto-theme-glossary/glossary-search.png`
- `output/playwright/crypto-theme-glossary/glossary-amber-theme.png`
- `output/playwright/crypto-theme-glossary/glossary-violet-theme.png`
- `output/playwright/crypto-theme-glossary/sol-horizons-compact.png`
- `output/playwright/sports-guide-audit/mlb-prop-filter-desktop.png`
- `output/playwright/sports-guide-audit/mlb-prop-filter-compact-600.png`

The screenshots intentionally reflect the current evidence: shadow execution,
expired live authorization, negative realized performance, and stale-feed
counts where present. The UI does not convert those states into a live-ready
claim.
