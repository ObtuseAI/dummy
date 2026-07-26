"""UI contract for the bounded Phase-2.3/2.4 operator evidence panes."""

import json

import pytest

from autonomy.dashboard_ui import DASHBOARD_HTML


def _between(start: str, end: str) -> str:
    return DASHBOARD_HTML.split(start, 1)[1].split(end, 1)[0]


def test_system_health_uses_the_versioned_fail_closed_status_contract():
    body = DASHBOARD_HTML
    block = _between(
        "function renderSystemHealth()",
        "function systemHealthCard()",
    )

    assert "st.system_health" in block
    assert "evidenceContractState(sh,true)" in block
    assert "item.schema_version!==1" in body
    assert "'AVAILABLE'" in body
    assert "'PARTIAL'" in body
    assert "'UNAVAILABLE'" in body

    assert "ledger.size_gib" in block
    assert "growth.sample_count" in block
    assert "growthSamples>=2" in block
    assert "growth.bytes_per_hour" in block
    assert "sqlite.retry_events_status" in block
    assert "sqlite.retry_events" in block
    assert "deadlines.records_considered" in block
    assert "deadlineTotal>0" in block
    assert "deadlines.rate" in block

    assert "retention.last_run_at" in block
    assert "retention.last_success_at" in block
    assert "retention.next_due_at" in block
    assert "promotion.run_status" in block
    assert "promotion.execution_authority===false" in block
    assert "no execution authority" in block

    assert "<b>Source:</b>" in body
    assert "<b>Window:</b>" in body
    assert "<b>Staleness:</b>" in body


def test_edge_quality_refuses_to_infer_distribution_or_actionable_share():
    distribution = _between(
        "function renderAfterFeeDistribution(afterFee)",
        "function actionableShareEvidence(actionable)",
    )
    actionable = _between(
        "function actionableShareEvidence(actionable)",
        "function executionCohortPane(cohort,kind)",
    )
    edge = _between(
        "function renderEdgeQuality()",
        "function edgeQualityCard()",
    )

    assert "st.edge_quality" in edge
    assert "evidenceContractState(eq,true)" in edge
    assert "afterFee.sample_count" in distribution
    assert "sampleCount>0" in distribution
    assert "binTotal===sampleCount" in distribution
    assert "zero validated after-fee rows" in distribution
    assert "raw edge value or zero-row sample is not substituted" in distribution

    assert "denominator>0" in actionable
    assert "numerator<=denominator" in actionable
    assert "Math.abs(value-numerator/denominator)<=0.0002" in actionable
    assert "actionableView.available" in edge
    assert "Actionable share UNAVAILABLE" in edge
    assert "No percentage is inferred from raw edge or incomplete counts." in edge


def test_execution_and_kxsol_evidence_remain_separated_and_non_authoritative():
    body = DASHBOARD_HTML
    comparison = _between(
        "function renderExecutionComparison(comparison)",
        "function renderKxsol15m(kx)",
    )
    kxsol = _between(
        "function renderKxsol15m(kx)",
        "function renderEdgeQuality()",
    )

    assert "comparison.audit_only===true" in comparison
    assert "comparison.policy_switch_authority===false" in comparison
    assert "AUDIT ONLY" in comparison
    assert "STALE" in comparison
    assert "cannot switch policy, promote a model, or authorize execution" in comparison
    assert "Witnessed maker (C0)" in body
    assert "Counterfactual taker (C1)" in body
    assert "Replay counterfactual; it is not a second realized book." in body

    assert 'caps.matched_series===\'KXSOL15M\'' in kxsol
    assert "mappingState.label!=='UNAVAILABLE'" in kxsol
    assert "stats.execution_authority===false" in kxsol
    assert "caps.execution_authority===false" in kxsol
    assert "Statistical scope" in kxsol
    assert "Caps exact-series evidence" in kxsol
    assert "Live authority &amp; session" in kxsol
    assert "Statistical evidence cannot authorize trading." in kxsol
    assert "Positive caps candidacy is one predicate only" in kxsol
    assert "statistics do not authorize orders." in kxsol
    assert "kx.execution_authority===false" in kxsol


def test_ops_evidence_renderers_are_get_only_and_refresh_on_contract_change():
    body = DASHBOARD_HTML
    system = _between(
        "function renderSystemHealth()",
        "function systemHealthCard()",
    )
    edge = _between(
        "function renderEdgeQuality()",
        "function edgeQualityCard()",
    )

    for block in (system, edge):
        assert "fetch(" not in block
        assert "/api/live-submit" not in block
        assert "<button" not in block
        assert "<input" not in block
        assert "method=" not in block

    assert "STATE.status&&STATE.status.system_health" in body
    assert "STATE.status&&STATE.status.edge_quality" in body
    assert "systemHealthCard()+edgeQualityCard()" in body


def test_p1_fail_closed_states_are_explicit_in_source_contract():
    body = DASHBOARD_HTML
    summary = _between("function statusSummary()", "function statusRibbon()")
    edge = _between("function renderEdgeQuality()", "function edgeQualityCard()")

    assert "'EVIDENCE_ONLY','EXACT_TAXONOMY'" in body
    assert "wd.healthy===true&&accountFresh" in summary
    assert "accountAge.stale===false" in summary
    assert "wd.healthy!==false" not in summary
    assert "accountAge.stale!==true" not in summary

    assert "board.stale===false&&boardArtifactStatus==='FRESH'" in edge
    assert "contractBoardCurrent?safeEvidenceRows(board.gate_reason_counts)" in edge
    assert "Stored reasons are not rendered as current." in edge
    assert "Fresh complete-board reason count" in edge
    assert "Validated complete-board reason count" not in edge


@pytest.fixture
def dashboard_browser_page():
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        playwright = sync_api.sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except sync_api.Error as exc:
        pytest.skip(f"bundled Chromium is unavailable: {exc}")

    page = browser.new_page()
    empty_payloads = {
        "/api/overview": {},
        "/api/scopes": {},
        "/api/status": {},
        "/api/walk_forward": {"leagues": {}},
        "/api/bet_board": {"groups": {}},
        "/api/model-arsenal": {},
        "/api/tier-performance": {},
    }

    def serve(route):
        path = route.request.url.removeprefix("http://dummy.test")
        if path in {"", "/"}:
            route.fulfill(
                status=200,
                content_type="text/html",
                body=DASHBOARD_HTML,
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(empty_payloads.get(path, {})),
        )

    page.route("http://dummy.test/**", serve)
    page.goto("http://dummy.test/", wait_until="domcontentloaded")
    page.wait_for_function(
        "() => typeof renderEdgeQuality === 'function' "
        "&& typeof statusSummary === 'function'"
    )
    try:
        yield page
    finally:
        browser.close()
        playwright.stop()


def test_browser_executes_evidence_gate_and_headline_fail_closed_contract(
    dashboard_browser_page,
):
    page = dashboard_browser_page
    kxsol = {
        "status": "EVIDENCE_ONLY",
        "series": "KXSOL15M",
        "scope_mapping": {
            "status": "EXACT_TAXONOMY",
            "scope": "crypto_patience_confirm|sol|15m_direction|15m",
            "source": "autonomy.taxonomy.grading_scope",
        },
        "statistical_evidence": {
            "status": "AVAILABLE",
            "classification": "edge",
            "clusters": 99,
            "edge_mean": 0.04,
            "ci_lower": 0.01,
            "ci_upper": 0.07,
            "stale": False,
            "execution_authority": False,
        },
        "caps_evidence": {
            "status": "AVAILABLE",
            "exact_series_allowed": True,
            "matched_series": "KXSOL15M",
            "execution_authority": False,
        },
        "live_authority": {
            "state": "default_disabled",
            "execution_authority": False,
            "session_status": "NO_SESSION_FILE",
        },
        "execution_authority": False,
    }
    kxsol_html = page.evaluate("(value) => renderKxsol15m(value)", kxsol)
    assert "crypto_patience_confirm|sol|15m_direction|15m" in kxsol_html
    assert ">edge<" in kxsol_html
    assert "Statistical evidence cannot authorize trading." in kxsol_html
    assert "scope UNAVAILABLE" not in kxsol_html

    def rendered_edge(board):
        return page.evaluate(
            """(currentBoard) => {
                STATE.status = {
                    generated_at: new Date().toISOString(),
                    recent_cycles: [],
                    edge_quality: {
                        schema_version: 1,
                        status: 'PARTIAL',
                        current_board: currentBoard,
                        execution_comparison: {status: 'UNAVAILABLE'},
                        kxsol15m: {status: 'UNAVAILABLE'}
                    }
                };
                STATE.board = {};
                STATE.boardMeta = {};
                return renderEdgeQuality();
            }""",
            board,
        )

    unsafe_reason = {
        "tier": "UNATTRIBUTED",
        "reason": "P1_REASON_MUST_NOT_RENDER",
        "count": 7,
    }
    for board in (
        {},
        {
            "status": "UNAVAILABLE",
            "artifact_status": "INVALID",
            "stale": True,
            "gate_reason_counts": [unsafe_reason],
        },
        {
            "status": "STALE",
            "artifact_status": "STALE",
            "stale": True,
            "gate_reason_counts": [unsafe_reason],
        },
    ):
        html = rendered_edge(board)
        assert "P1_REASON_MUST_NOT_RENDER" not in html
        assert "Stored reasons are not rendered as current." in html

    fresh_html = rendered_edge(
        {
            "status": "PARTIAL",
            "artifact_status": "FRESH",
            "stale": False,
            "gate_reason_counts": [
                {"tier": "UNATTRIBUTED", "reason": "FRESH_REASON", "count": 2}
            ],
        }
    )
    assert "FRESH_REASON" in fresh_html
    assert "Fresh complete-board reason count" in fresh_html

    health_cases = [
        ({}, {"stale": False}, False),
        ({"healthy": True}, {}, False),
        ({"healthy": True}, {"stale": True}, False),
        ({"healthy": False}, {"stale": False}, False),
        ({"healthy": True}, {"stale": False}, True),
    ]
    for watchdog, account_age, expected in health_cases:
        healthy = page.evaluate(
            """([watchdog, accountAge]) => {
                STATE.status = {
                    generated_at: new Date().toISOString(),
                    heartbeat: {},
                    watchdog,
                    data_ages: {live_account: accountAge},
                    session: {},
                    live_controls: {execution_authority: false}
                };
                return statusSummary().healthy;
            }""",
            [watchdog, account_age],
        )
        assert healthy is expected
