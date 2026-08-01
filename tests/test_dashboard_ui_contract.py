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


def test_overview_catalog_names_all_capabilities_and_crypto_loops():
    body = DASHBOARD_HTML

    assert "function capabilityCatalog()" in body
    assert 'aria-label="Complete capability catalog"' in body
    assert "All abilities" in body
    assert "DummyCryptoPaperTwin (5-minute)" in body
    assert "DummyCryptoHorizonEvidence (10-minute)" in body
    assert "Multi-timeframe research charts" in body
    assert "BTC, ETH, and SOL closed candles across 15m, 1h, 4h, 1d, and 1w" in body
    for capability in (
        "Market perception",
        "Seven-league intelligence",
        "Probability engines",
        "Model Arsenal + dissent",
        "Trust + uncertainty",
        "Walk-forward + backtests",
        "Portfolio construction",
        "Risk + execution firewall",
        "Settlement + audit memory",
        "Autoresearch + evolution",
        "Metacognition + self-scout",
        "Fleet reliability",
        "Operator experience",
        "Observer MCP",
    ):
        assert capability in body
    segment = body.split("function capabilityCatalog()", 1)[1].split(
        "\nfunction overviewView()", 1
    )[0]
    assert "fetch(" not in segment
    error_branch = body.split("function overviewView()", 1)[1].split(
        "const account=o.live_account", 1
    )[0]
    assert "+capabilityCatalog()" in error_branch


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
    assert "openai/gpt-5.6-terra" not in body  # roster comes from the local API
    assert "Opening or refreshing it never sends a prompt" in body
    assert "A valid key and 4/4 smoke prove bounded reachability only" in body
    assert "Evidence authority" in body
    assert "Probability authority" in body
    assert "Order authority" in body
    assert "two_key_paid_call_gate_open" in body
    assert "background_panel_ready" in body
    assert "fetch('/api/model-arsenal'" not in body
    assert ".map(get)" in body


def test_organism_cleanup_removes_dead_ui_and_matches_poll_cadence():
    body = DASHBOARD_HTML

    assert "function areaChart(" not in body
    assert "function pickBoardCard(" not in body
    assert "function pickRows(" not in body
    assert "every 20 min" not in body
    assert "every 20 seconds" in body


def test_gl_engine_has_real_webgl2_shaders_and_tiered_fallbacks():
    body = DASHBOARD_HTML

    assert (
        '<div id="scene" role="img" '
        'aria-label="Live map of Dummy scopes, signals, and engine health">'
    ) in body
    assert '<canvas id="gl" aria-hidden="true"></canvas>' in body
    assert '<canvas id="fx" aria-hidden="true"' in body
    assert "const GL_TIER={STATIC:0,CANVAS2D:1,WEBGL:2,WEBGL_BLOOM:3}" in body
    assert "function bootGL(" in body
    assert "getContext('webgl2'" in body
    assert "getContext('webgl'" in body
    assert "function glslFor(" in body
    assert "#version 300 es" in body
    assert "webglcontextlost" in body
    assert "function probeTier(" in body
    assert "function drawOnce(" in body
    assert "function startFx2D(" in body
    assert "function drawFxOrganism(" in body
    assert "document.body.dataset.sceneTier" in body
    assert "visibilitychange" in body


def test_scene_model_binds_only_real_polled_fields():
    body = DASHBOARD_HTML

    assert "function sceneModel()" in body
    segment = body.split("function sceneModel()", 1)[1].split(
        "// ambient dust", 1
    )[0]
    assert "fetch(" not in segment
    assert "Math.random" not in segment
    assert "contested_n" in segment
    assert "brier_edge" in segment
    assert "active_sources" in segment
    assert "sports_model_seed" in segment
    assert "function makeDust(" in body
    assert "function glBuild(" in body
    assert "byScope" in body


def test_event_bridge_emits_only_from_polled_diffs():
    body = DASHBOARD_HTML

    assert "// ---------- EVENTS ----------" in body
    assert "const EV={map:{}}" in body
    assert "function watchSnapshot()" in body
    assert "function watchDiff(" in body
    assert "prevWatch" in body
    segment = body.split("function watchDiff(", 1)[1].split(
        "// pulses:", 1
    )[0]
    assert "fetch(" not in segment
    assert "EV.emit('scope:changed'" in segment
    assert "EV.emit('freshness:changed'" in segment
    assert "watchDiff(watchSnapshot())" in body
    assert "function glPulse(" in body
    assert "EV.on('scope:changed'" in body
    assert "glSetMood" in body


def test_camera_flies_to_route_targets_and_respects_reduced_motion():
    body = DASHBOARD_HTML

    assert "function flyTo(" in body
    assert "function scopePreset(" in body
    assert "function syncCameraToRoute(" in body
    assert "CAM_PRESETS" in body
    segment = body.split("function flyTo(", 1)[1].split(
        "\nfunction scopePreset(", 1
    )[0]
    assert "REDUCE" in segment
    render_segment = body.split("function render(", 1)[1].split(
        "\nfunction kpi(", 1
    )[0]
    assert "syncCameraToRoute(" in render_segment


def test_organism_layout_keeps_truth_and_navigation_accessible():
    body = DASHBOARD_HTML

    assert "/* ---------- organism layout ---------- */" in body
    assert ".opsbar{position:sticky;top:12px" in body
    assert "@media(min-width:921px)" in body
    assert ".side{width:78px" in body
    assert ".side:hover,.side:focus-within{width:264px}" in body
    assert '<div class="dockband">' in body


def test_scope_views_dock_without_dropping_existing_panels():
    body = DASHBOARD_HTML

    assert "function scopeViewInner(" in body
    assert (
        "function scopeView(vert,label){return "
        '\'<div class="dock">\'+scopeViewInner(vert,label)+\'</div>\';}'
    ) in body
    assert ".dock{margin-left:" in body
    for function_call in (
        "dailyGuideCard(label)",
        "tierPerformanceCard(label)",
        "cryptoHorizonCard(label)",
        "accuracyBars(s)",
        "picksTable(sc.picks)",
        "betTypeCard(sc.bet_types)",
        "settledTodayCard(sc)",
    ):
        assert function_call in body


def test_palette_themes_recolor_the_scene_without_changing_poll_contract():
    body = DASHBOARD_HTML

    theme_segment = body.split("function setTheme(a)", 1)[1].split(
        "\n(function()", 1
    )[0]
    assert "glBuild(sceneModel())" in theme_segment
    assert "GT.model=sceneModel()" in theme_segment
    assert "'Theme: '+a" in body
    assert "r.action" in body
    assert "A requires at least 4% edge after the quoted ask" in body
    assert (
        "Promise.allSettled(['/api/overview','/api/scopes','/api/status',"
        "'/api/walk_forward','/api/bet_board','/api/model-arsenal',"
        "'/api/tier-performance'].map(get))"
    ) in body
    assert "results.slice(0,6)" in body
    assert "results[6]" in body
    assert "setInterval(poll,20000)" in body
