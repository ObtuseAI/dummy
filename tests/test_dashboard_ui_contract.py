"""Regression checks for the desktop operator board's UX truth contract."""

from autonomy.dashboard_ui import DASHBOARD_HTML


def test_operator_board_is_outcome_first_and_accessible():
    body = DASHBOARD_HTML

    assert "Live account observer active — submit locked" in body
    assert "['live_account','sports_model_seed'].includes(k)" in body
    assert "['heartbeat','live_account'].includes(k)" not in body
    assert "Live Kalshi account" in body
    assert "page requests never query Kalshi" in body
    assert "account.http_proof" in body
    assert "Paper history retired" in body
    assert "RETIRED_NON_AUTHORITATIVE" in body
    assert "Paper account" not in body
    assert "Realized P&amp;L" not in body
    assert "Promoted for execution" not in body
    assert "Close to promotion" not in body
    assert "paper_account_as_of||o.generated_at" not in body
    assert "performance_evidence_as_of||o.generated_at" not in body

    assert 'class="skip" href="#main"' in body
    assert 'aria-label="Primary navigation"' in body
    assert 'aria-label="Execution authority"' in body
    assert 'role="dialog" aria-modal="true"' in body
    assert 'role="listbox"' in body


def test_system_health_and_edge_quality_are_bounded_read_only_evidence():
    body = DASHBOARD_HTML

    assert "function systemHealthCard()" in body
    assert "typeof wd.healthy==='boolean'" in body
    assert "v.stale===true" in body
    assert "safeEvidenceRows(st.alerts).slice(-5).reverse()" in body
    assert "safeEvidenceRows(st.recent_cycles).slice(-5).reverse()" in body
    assert "Alert history is empty or unavailable" in body
    assert "Recent-cycle evidence is unavailable. No successful or healthy cycle is inferred." in body

    assert "function edgeQualityCard()" in body
    assert "['markets_scanned','signals_generated','signals_rejected','decisions_made','abstained']" in body
    assert "Cycle-level reason distribution unavailable" in body
    assert "['WATCH','UNATTRIBUTED'].includes(tier)" in body
    assert "gates.reasons.slice(0,5)" in body
    assert "not cycle causes" in body
    assert "no reason is inferred" in body
    assert "systemHealthCard()+edgeQualityCard()" in body

    health_block = body.split("function systemHealthCard()", 1)[1].split(
        "function currentBoardRows()", 1
    )[0]
    edge_block = body.split("function edgeQualityCard()", 1)[1].split(
        "function overviewView()", 1
    )[0]
    assert "fetch(" not in health_block
    assert "fetch(" not in edge_block


def test_canonical_board_replaces_mobile_app_and_dead_ticker_cleanly():
    body = DASHBOARD_HTML

    assert '<meta name="viewport"' in body
    assert "@media(max-width:480px)" in body
    assert ".side{position:fixed;z-index:20;inset:auto 0 0;height:64px" in body
    assert ".stage{height:calc(100vh - 64px)" in body
    assert 'class="sub">operator board</div>' in body
    assert "buildTape" not in body
    assert 'id="tape"' not in body


def test_high_cardinality_market_panels_are_lazy_and_bounded():
    body = DASHBOARD_HTML

    assert ".slice(0,100)" in body
    assert 'data-kind="guide"' in body
    assert "function dailyGuideCard(label)" in body
    assert "click any matchup for market breakdown" in body
    assert ".game{flex:0 0 auto" in body
    assert "Showing the 100 most recent" in body


def test_prediction_navigation_is_crypto_and_sports_only():
    body = DASHBOARD_HTML

    assert "const VERTICAL_META={CRYPTO:['coin','Crypto'],SPORTS:['ball','Sports']}" in body
    assert "COMMODITIES:['market','Commodities']" not in body
    assert "WEATHER:['weather','Weather']" not in body
    assert "const keys=['CRYPTO','SPORTS'].filter" in body


def test_sports_roster_is_visible_before_hydration_and_in_jump_menu():
    body = DASHBOARD_HTML

    assert "const SPORTS_ROSTER=['MLB','WNBA','NBA','NFL','NHL','NCAAF','NCAAMB']" in body
    assert "function sportsRoster()" in body
    assert "key==='SPORTS'||v[key]" in body
    assert "[...have,...sportsRoster()]" in body
    assert "scopeLabels(vert,vb).forEach" in body
    assert "season==='upcoming'?'pre'" in body
    assert "year-round capability fallback" in body.lower()


def test_daily_guide_uses_event_date_and_honest_empty_state():
    body = DASHBOARD_HTML

    assert "function rowEventDate(r)" in body
    assert "Today’s '+esc(label)+' betting guide" in body
    assert "No '+esc(label)+' events are listed for today." in body
    assert "const active=todayRows" in body
    assert "Future-dated markets are intentionally excluded" in body
    assert "Next slate preview:" not in body
    assert "futureDates" not in body
    assert "function gameBreakdown(rows)" in body


def test_daily_guide_filters_every_layer_and_keeps_selection():
    body = DASHBOARD_HTML

    assert "let GUIDE_FILTERS={}" in body
    assert "GUIDE_FILTERS[card.dataset.league]" in body
    assert "data-market-type=" in body
    assert "gameBreakdown(ranked)" in body
    assert "Filtered to <b>" in body
    assert "choose All markets for the complete board" in body
    assert "ArrowRight" in body and "ArrowLeft" in body
    assert "function revealGuideTab(tab,smooth)" in body


def test_daily_guide_prop_rows_use_named_market_display():
    body = DASHBOARD_HTML

    assert "function marketName(r)" in body
    assert "r.title).match" in body
    assert "esc(marketName(best))" in body
    assert "esc(marketName(r))" in body


def test_sports_guide_keeps_current_tier_grades_visible_without_result_report():
    body = DASHBOARD_HTML

    assert "function boardTierCounts(scope)" in body
    assert "coverageDate&&String((row||{}).event_date||'')!==coverageDate" in body
    assert "counts=boardCounts.available?boardCounts.counts:tierScopeCounts" in body
    assert "Current grades come from the visible board snapshot" in body
    assert "RESULT EVIDENCE UNAVAILABLE" in body
    assert "Current A/B/C/WATCH/UNATTRIBUTED counts above still come directly" in body


def test_primary_tier_card_is_forecast_only_after_paper_retirement():
    body = DASHBOARD_HTML

    assert "Tier forecast diagnostics" in body
    assert "tp.tier_performance_generated_at||tp.evidence_generated_at" in body
    assert "Paper/shadow realized economics are retired" in body
    assert "Realized n" not in body
    assert "Net P&amp;L" not in body
    assert "ROI on cost" not in body


def test_sports_matchups_surface_tier_counts_and_row_reasons_before_promotion():
    body = DASHBOARD_HTML

    assert "function gameTierSummary(rows)" in body
    assert 'aria-label="Tier counts: ' in body
    assert "gameTierSummary(ranked)" in body
    assert "Tier / reason" in body
    assert "boardTierReason(r)" in body
    assert "WATCH — below 1% executable net edge" in body


def test_missing_tier_result_artifact_is_not_generic_dashboard_degradation():
    body = DASHBOARD_HTML

    assert "const failed=results.slice(0,6).filter" in body
    assert "STATE.tierPerformanceFetchOk=results[6].status==='fulfilled'" in body
    assert "STATE.tierPerformanceFetchOk" in body


def test_crypto_horizons_are_visible_and_evidence_gated():
    body = DASHBOARD_HTML

    assert "function cryptoHorizonCard(asset)" in body
    assert "['1h','Hourly'],['1d','Daily'],['1w','Weekly']" in body
    assert "Normal positions still require positive fee- and uncertainty-adjusted EV." in body
    assert "retired paper observer supplies research coverage only" in body
    assert "it never contacts the broker" in body


def test_color_controls_switch_the_complete_saved_theme():
    body = DASHBOARD_HTML

    assert 'data-theme="emerald"' in body
    assert "html[data-theme=amber]" in body
    assert "html[data-theme=cyan]" in body
    assert "html[data-theme=violet]" in body
    assert "function setTheme(a)" in body
    assert "localStorage.setItem('dummy-theme',a)" in body
    assert 'aria-label="Application theme"' in body


def test_glossary_route_explains_terms_and_workflow():
    body = DASHBOARD_HTML

    assert "#/glossary" in body
    assert "function glossaryView()" in body
    assert "function wireGlossary()" in body
    assert "Glossary & how Dummy works" in body
    assert "Brier score" in body
    assert "Data-only source" in body
    assert "Equity valuation" not in body
    assert "valuation packet" not in body


def test_model_arsenal_is_primary_read_only_and_authority_separated():
    body = DASHBOARD_HTML

    assert "#/arsenal" in body
    assert "function modelArsenalView()" in body
    assert "function modelArsenalSummaryCard()" in body
    assert "Model Arsenal" in body
    assert "/api/model-arsenal" in body
    assert "google/gemini-3.6-flash" not in body  # roster comes from the local API
    assert "Opening or refreshing it never sends a prompt" in body
    assert "A valid key and 4/4 smoke prove bounded reachability only" in body
    assert "Evidence authority" in body
    assert "Probability authority" in body
    assert "Order authority" in body
    assert "two_key_paid_call_gate_open" in body
    assert "background_panel_ready" in body
    assert "fetch('/api/model-arsenal'" not in body
    assert ".map(get)" in body
