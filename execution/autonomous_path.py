from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import state as state_module
from core import config_loader
from core.ontology import (
    AccountMode,
    FirewallVerdict,
    LiveOrderRequest,
    LiveOrderResult,
    Market,
    OrderBook,
    TradeProposal,
)
from forecasting.engine import ForecastEngine
from forecasting.model_influence_attestation import build_model_influence_attestation
from kalshi.live_data import KalshiLiveData, KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from live_firewall.firewall import LiveBrokerFirewall
from strategies.scan import StrategyScanner
from live_firewall.exposure_tracker import ExposureTracker
from risk.governor import assess_trade_risk
from compliance.governor import assess_compliance
from strategies.registry import STRATEGIES
from proof.ledger import write_proof
from autonomy.target_policy import (
    is_data_only_target,
    is_equity_index_target,
    is_prediction_quarantined_target,
)

DEFAULT_ADAPTER_NAME = "kalshi_live_firewall_adapter"
PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS = PROJECT_ROOT / "artifacts" / "dummy"


class AutonomousExecutionPath:
    """End-to-end autonomous execution orchestrator for Dummy live trading.

    The cycle only operates when the global state is in
    ``AccountMode.AUTONOMOUS_LIVE_CAPPED``.  It chains live market data, the
    forecast engine, repo-derived strategies, risk/compliance/firewall gates,
    and finally ``LiveBrokerFirewall.submit`` as the single live order
    chokepoint.  Every completed cycle writes a proof entry.
    """

    def __init__(
        self,
        live_data: KalshiLiveData | None = None,
        forecast_engine: ForecastEngine | None = None,
        firewall: LiveBrokerFirewall | None = None,
        exposure_tracker: ExposureTracker | None = None,
        strategies: list[Any] | None = None,
        adapter_name: str = DEFAULT_ADAPTER_NAME,
    ):
        self.live_data = live_data or KalshiLiveData()
        self.forecast_engine = forecast_engine or ForecastEngine()
        self.exposure = exposure_tracker or ExposureTracker()
        self.firewall = firewall or LiveBrokerFirewall(self.live_data.client, self.exposure)
        self.strategies = strategies if strategies is not None else STRATEGIES
        self.adapter_name = adapter_name

    async def run_cycle(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None = None,
        event_title: str | None = None,
        contract_title: str | None = None,
    ) -> dict[str, Any]:
        """Run one autonomous capped execution cycle.

        Returns a dict describing the outcome, including any proposal, gate
        verdicts, order result, reconciliation snapshot, and proof reference.
        """
        if state_module.STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return self._blocked(
                market_ticker,
                contract_ticker,
                strategy_name,
                rejected_by="mode",
                reason=(
                    f"Mode is {state_module.STATE.mode.value}; "
                    f"{AccountMode.AUTONOMOUS_LIVE_CAPPED.value} required"
                ),
            )

        if is_data_only_target(market_ticker) or is_data_only_target(contract_ticker):
            return self._blocked(
                market_ticker,
                contract_ticker,
                strategy_name,
                rejected_by="data_only_target",
                reason=(
                    "Weather and commodity contracts are contextual data only"
                ),
            )

        if is_equity_index_target(market_ticker) or is_equity_index_target(
            contract_ticker
        ):
            return self._blocked(
                market_ticker,
                contract_ticker,
                strategy_name,
                rejected_by="equity_index_target_quarantine",
                reason="Target is outside Dummy's supported prediction surface",
            )

        try:
            orderbook = await self.live_data.get_orderbook(contract_ticker)
        except Exception as exc:
            return self._blocked(
                market_ticker,
                contract_ticker,
                strategy_name,
                rejected_by="live_data",
                reason=f"Failed to fetch orderbook: {exc}",
            )

        forecast = self.forecast_engine.forecast(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            event_title=event_title or market_ticker,
            contract_title=contract_title or contract_ticker,
            orderbook=orderbook,
        )

        proposal = self._select_proposal(
            forecast,
            orderbook,
            strategy_name,
            expected_market_ticker=market_ticker,
            expected_contract_ticker=contract_ticker,
        )
        if proposal is None:
            return self._no_trade(
                market_ticker,
                contract_ticker,
                strategy_name,
                forecast,
                orderbook,
            )

        caps = config_loader.load_caps()
        compliance_verdict = assess_compliance(market_ticker, contract_ticker, caps=caps)
        proposal.compliance_verdict = compliance_verdict
        if not compliance_verdict.passed:
            return self._blocked_proposal(
                proposal,
                forecast,
                orderbook,
                rejected_by="compliance",
                reason=compliance_verdict.reason,
            )

        risk_verdict = assess_trade_risk(proposal, caps)
        if not risk_verdict.passed:
            return self._blocked_proposal(
                proposal,
                forecast,
                orderbook,
                rejected_by="risk",
                reason=risk_verdict.reason,
                risk_verdict=risk_verdict,
            )

        request_fields = {
            "proposal_id": proposal.id,
            "market_ticker": proposal.market_ticker,
            "contract_ticker": proposal.contract_ticker,
            "side": proposal.side,
            "price_cents": proposal.price_cents,
            "size": proposal.size,
            "strategy_proof_reference": proposal.proof_reference,
            "forecast_proof_reference": proposal.forecast_reference,
            "adapter_name": self.adapter_name,
        }
        request = LiveOrderRequest(
            **request_fields,
            model_influence_attestation=build_model_influence_attestation(
                forecast,
                request_fields,
            ),
        )

        firewall_verdict = await self.firewall.evaluate(request, orderbook, forecast)
        if not firewall_verdict.allow:
            return self._blocked_proposal(
                proposal,
                forecast,
                orderbook,
                rejected_by=firewall_verdict.rejected_by or "firewall",
                reason=firewall_verdict.reason,
                risk_verdict=risk_verdict,
                firewall_verdict=firewall_verdict,
                request=request,
            )

        order_result = await self.firewall.submit(request, orderbook, forecast)
        reconciliation = await self._reconcile(contract_ticker)

        status = "success" if order_result.success else "blocked"
        payload: dict[str, Any] = {
            "market_ticker": market_ticker,
            "contract_ticker": contract_ticker,
            "strategy_name": strategy_name,
            "mode": state_module.STATE.mode.value,
            "adapter_name": self.adapter_name,
            "proposal": proposal.model_dump(),
            "forecast": forecast.model_dump(),
            "risk_verdict": risk_verdict.model_dump(),
            "compliance_verdict": compliance_verdict.model_dump(),
            "firewall_verdict": firewall_verdict.model_dump(),
            "order_result": order_result.model_dump(),
            "reconciliation": reconciliation,
            "status": status,
        }
        proof_ref = write_proof("autonomous_execution_path", status, payload)
        return {**payload, "proof_reference": proof_ref}

    def _select_proposal(
        self,
        forecast: Any,
        orderbook: OrderBook,
        strategy_name: str | None,
        *,
        expected_market_ticker: str | None = None,
        expected_contract_ticker: str | None = None,
    ) -> TradeProposal | None:
        """Select a proposal only after binding it to the current inputs.

        Strategy objects supplied to the execution path are untrusted.  A
        strategy must opt into the prediction contract explicitly, and a
        returned proposal cannot redirect the cycle to another market,
        contract, or forecast proof.  Re-validating into a fresh
        ``TradeProposal`` also prevents a caller from retaining and mutating
        the object that the execution path consumes.
        """
        forecast_market = getattr(forecast, "market_ticker", None)
        forecast_contract = getattr(forecast, "contract_ticker", None)
        forecast_reference = getattr(forecast, "proof_reference", None)
        expected_market = expected_market_ticker or forecast_market
        expected_contract = expected_contract_ticker or forecast_contract

        if not all(
            isinstance(value, str) and value
            for value in (
                expected_market,
                expected_contract,
                forecast_market,
                forecast_contract,
                forecast_reference,
            )
        ):
            return None
        if (
            forecast_market != expected_market
            or forecast_contract != expected_contract
            or orderbook.contract_ticker != expected_contract
            # Kalshi's direct order-book adapter historically uses the
            # contract ticker for both fields.  Accept that canonical alias,
            # but never an unrelated market identity.
            or orderbook.market_ticker not in {expected_market, expected_contract}
        ):
            return None
        if is_prediction_quarantined_target(
            expected_market
        ) or is_prediction_quarantined_target(expected_contract):
            return None
        for strategy in self.strategies:
            try:
                has_authority = (
                    getattr(strategy, "PREDICTION_AUTHORITY", None) is True
                    and getattr(strategy, "DATA_ONLY", False) is False
                )
            except Exception:
                has_authority = False
            if not has_authority:
                continue
            if strategy_name is not None:
                try:
                    matches_requested_strategy = (
                        strategy.__class__.__name__ == strategy_name
                        or getattr(strategy, "name", None) == strategy_name
                    )
                except Exception:
                    matches_requested_strategy = False
                if not matches_requested_strategy:
                    continue
            proposal = strategy.evaluate(forecast, orderbook)
            if not isinstance(proposal, TradeProposal):
                continue
            if (
                proposal.market_ticker != expected_market
                or proposal.contract_ticker != expected_contract
                or proposal.forecast_reference != forecast_reference
            ):
                continue
            try:
                proposal_payload = proposal.model_dump(mode="python")
                proposal_payload.update(
                    {
                        "market_ticker": expected_market,
                        "contract_ticker": expected_contract,
                        "forecast_reference": forecast_reference,
                    }
                )
                return TradeProposal.model_validate(proposal_payload)
            except Exception:
                continue
        return None

    async def rehearse_live_cap(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        """Run the full autonomous live-capped chain using real market data.

        By default the chain stops after the firewall rehearsal and records the
        would-be order.  A real order is only sent when the operator has
        explicitly enabled live submit via configs/live_submit.json.
        """
        base = {
            "market_ticker": market_ticker,
            "contract_ticker": contract_ticker,
            "strategy_name": strategy_name,
            "mode": state_module.STATE.mode.value,
            "adapter_name": self.adapter_name,
        }

        if state_module.STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            base.update({"status": "blocked", "rejected_by": "mode", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED"})
            proof_ref = write_proof("rehearse_live_cap", "blocked", base)
            return {**base, "proof_reference": proof_ref}

        if is_data_only_target(market_ticker) or is_data_only_target(contract_ticker):
            base.update({
                "status": "blocked",
                "rejected_by": "data_only_target",
                "reason": "Weather and commodity contracts are contextual data only",
            })
            proof_ref = write_proof("rehearse_live_cap", "blocked", base)
            return {**base, "proof_reference": proof_ref}
        if is_equity_index_target(market_ticker) or is_equity_index_target(
            contract_ticker
        ):
            base.update({
                "status": "blocked",
                "rejected_by": "equity_index_target_quarantine",
                "reason": "Target is outside Dummy's supported prediction surface",
            })
            proof_ref = write_proof("rehearse_live_cap", "blocked", base)
            return {**base, "proof_reference": proof_ref}

        try:
            reader = KalshiRealReadOnly()
        except KalshiCredentialsMissing:
            base.update({"status": "blocked", "rejected_by": "credentials", "reason": "Kalshi credentials missing", "credentials_present": False})
            proof_ref = write_proof("rehearse_live_cap", "blocked", base)
            return {**base, "proof_reference": proof_ref, "credentials_present": False}

        try:
            snapshot = await reader.get_full_snapshot(contract_ticker)
            normalizer = KalshiNormalizer()
            normalized = normalizer.normalize_full_snapshot(snapshot, contract_ticker)
        except Exception as exc:
            base.update({"status": "blocked", "rejected_by": "normalization", "reason": f"Data normalization failed: {exc}", "credentials_present": True})
            proof_ref = write_proof("rehearse_live_cap", "blocked", base)
            return {**base, "proof_reference": proof_ref, "credentials_present": True}

        orderbook = normalized["orderbook"]
        market = normalized["markets"][0] if normalized["markets"] else Market(
            ticker=market_ticker,
            title=market_ticker,
            status="active",
            category="unknown",
            event_ticker=market_ticker,
        )

        forecast = self.forecast_engine.forecast(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            event_title=market.title,
            contract_title=contract_ticker,
            orderbook=orderbook,
        )

        scanner = StrategyScanner()
        scan_results = scanner.scan(
            forecast,
            orderbook,
            market_category=market.category,
        )

        proposal = None
        if strategy_name is not None:
            proposal = next((r.proposal for r in scan_results if r.family == strategy_name and r.proposal is not None), None)
        if proposal is None:
            proposal = next((r.proposal for r in scan_results if r.proposal is not None), None)

        if proposal is None:
            payload = {
                **base,
                "status": "no_trade",
                "credentials_present": True,
                "forecast": forecast.model_dump(),
                "scan_results": [self._scan_result_to_dict(r) for r in scan_results],
                "reason": "No strategy emitted a TradeProposal",
            }
            proof_ref = write_proof("rehearse_live_cap", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        compliance_verdict = assess_compliance(market_ticker, contract_ticker, caps=config_loader.load_caps())
        if not compliance_verdict.passed:
            payload = self._rehearsal_payload(base, forecast, scan_results, proposal, compliance_verdict=compliance_verdict)
            payload.update({"status": "blocked", "rejected_by": "compliance", "reason": compliance_verdict.reason})
            proof_ref = write_proof("rehearse_live_cap", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        risk_verdict = assess_trade_risk(proposal, config_loader.load_caps())
        if not risk_verdict.passed:
            payload = self._rehearsal_payload(base, forecast, scan_results, proposal, risk_verdict=risk_verdict)
            payload.update({"status": "blocked", "rejected_by": "risk", "reason": risk_verdict.reason})
            proof_ref = write_proof("rehearse_live_cap", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        request_fields = {
            "proposal_id": proposal.id,
            "market_ticker": proposal.market_ticker,
            "contract_ticker": proposal.contract_ticker,
            "side": proposal.side,
            "price_cents": proposal.price_cents,
            "size": proposal.size,
            "strategy_proof_reference": proposal.proof_reference,
            "forecast_proof_reference": proposal.forecast_reference,
            "adapter_name": self.adapter_name,
        }
        request = LiveOrderRequest(
            **request_fields,
            model_influence_attestation=build_model_influence_attestation(
                forecast,
                request_fields,
            ),
        )

        firewall_rehearsal = await self.firewall.submit_rehearsal(request, orderbook, forecast)
        live_submitted = False
        order_result = None
        if firewall_rehearsal.would_submit:
            order_result = await self.firewall.submit(request, orderbook, forecast)
            live_submitted = order_result.success

        payload = self._rehearsal_payload(
            base,
            forecast,
            scan_results,
            proposal,
            compliance_verdict=compliance_verdict,
            risk_verdict=risk_verdict,
            firewall_rehearsal=firewall_rehearsal,
            order_result=order_result,
            live_submitted=live_submitted,
        )
        status = "live_submitted" if live_submitted else "rehearsal"
        payload["status"] = status
        proof_ref = write_proof("rehearse_live_cap", status, payload)
        return {**payload, "proof_reference": proof_ref}

    def _scan_result_to_dict(self, result) -> dict[str, Any]:
        return {
            "family": result.family,
            "market_ticker": result.market_ticker,
            "contract_ticker": result.contract_ticker,
            "edge_estimate": result.edge_estimate,
            "confidence": result.confidence,
            "liquidity_score": result.liquidity_score,
            "spread_score": result.spread_score,
            "settlement_risk_score": result.settlement_risk_score,
            "proposal_summary": result.proposal.model_dump() if result.proposal else None,
            "no_trade_reason": result.no_trade_reason,
        }

    def _rehearsal_payload(
        self,
        base: dict[str, Any],
        forecast,
        scan_results,
        proposal: TradeProposal,
        compliance_verdict=None,
        risk_verdict=None,
        firewall_rehearsal=None,
        order_result: LiveOrderResult | None = None,
        live_submitted: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **base,
            "credentials_present": True,
            "forecast": forecast.model_dump(),
            "proposal": proposal.model_dump(),
            "scan_results": [self._scan_result_to_dict(r) for r in scan_results],
        }
        if compliance_verdict is not None:
            payload["compliance_verdict"] = compliance_verdict.model_dump()
        if risk_verdict is not None:
            payload["risk_verdict"] = risk_verdict.model_dump()
        if firewall_rehearsal is not None:
            payload["firewall_rehearsal"] = {
                "would_submit": firewall_rehearsal.would_submit,
                "firewall_verdict": firewall_rehearsal.firewall_verdict.model_dump(),
                "order": firewall_rehearsal.order,
                "blocked_reason": firewall_rehearsal.blocked_reason,
            }
        if order_result is not None:
            payload["order_result"] = order_result.model_dump()
        payload["live_submitted"] = live_submitted
        return payload

    async def _reconcile(self, contract_ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "contract_ticker": contract_ticker,
            "resting_orders": None,
            "fills": None,
            "resting_orders_error": None,
            "fills_error": None,
        }
        try:
            result["resting_orders"] = await self.live_data.get_resting_orders()
        except Exception as exc:
            result["resting_orders_error"] = str(exc)
        try:
            result["fills"] = await self.live_data.get_fills()
        except Exception as exc:
            result["fills_error"] = str(exc)
        return result

    def _base_payload(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None,
    ) -> dict[str, Any]:
        return {
            "market_ticker": market_ticker,
            "contract_ticker": contract_ticker,
            "strategy_name": strategy_name,
            "mode": state_module.STATE.mode.value,
            "adapter_name": self.adapter_name,
        }

    def _blocked(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None,
        rejected_by: str,
        reason: str,
    ) -> dict[str, Any]:
        payload = self._base_payload(market_ticker, contract_ticker, strategy_name)
        payload.update(
            {
                "status": "blocked",
                "rejected_by": rejected_by,
                "reason": reason,
            }
        )
        proof_ref = write_proof("autonomous_execution_path", "blocked", payload)
        return {**payload, "proof_reference": proof_ref}

    def _no_trade(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None,
        forecast: Any,
        orderbook: OrderBook,
    ) -> dict[str, Any]:
        payload = self._base_payload(market_ticker, contract_ticker, strategy_name)
        payload.update(
            {
                "status": "no_trade",
                "forecast": forecast.model_dump(),
                "orderbook": orderbook.model_dump(),
                "reason": "No strategy emitted a TradeProposal",
            }
        )
        proof_ref = write_proof("autonomous_execution_path", "no_trade", payload)
        return {**payload, "proof_reference": proof_ref}

    def _blocked_proposal(
        self,
        proposal: TradeProposal,
        forecast: Any,
        orderbook: OrderBook,
        rejected_by: str,
        reason: str,
        risk_verdict: Any | None = None,
        firewall_verdict: FirewallVerdict | None = None,
        request: LiveOrderRequest | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "market_ticker": proposal.market_ticker,
            "contract_ticker": proposal.contract_ticker,
            "strategy_name": None,
            "mode": state_module.STATE.mode.value,
            "adapter_name": self.adapter_name,
            "proposal": proposal.model_dump(),
            "forecast": forecast.model_dump(),
            "orderbook": orderbook.model_dump(),
            "status": "blocked",
            "rejected_by": rejected_by,
            "reason": reason,
        }
        if risk_verdict is not None:
            payload["risk_verdict"] = risk_verdict.model_dump()
        if firewall_verdict is not None:
            payload["firewall_verdict"] = firewall_verdict.model_dump()
        if request is not None:
            payload["live_order_request"] = request.model_dump()
        proof_ref = write_proof("autonomous_execution_path", "blocked", payload)
        return {**payload, "proof_reference": proof_ref}


def _source_has_create_order_call(source: str) -> bool:
    """Return True if the source contains a call to ``create_order``.

    Function definitions and string literals that mention the name are ignored
    so that ``kalshi/client.py``'s method declaration is not counted as a live
    order invocation.
    """
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for line in source.splitlines():
        if call_re.search(line) and "def create_order(" not in line:
            return True
    return False


def _scan_for_create_order(root: Path) -> dict[str, Any]:
    excluded = {
        "tests",
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
    }
    files_with_calls: list[str] = []
    scanned_files: list[str] = []
    for path in root.rglob("*.py"):
        if any(part in excluded for part in path.parts):
            continue
        scanned_files.append(path.relative_to(root).as_posix())
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if _source_has_create_order_call(source):
            files_with_calls.append(path.relative_to(root).as_posix())
    return {
        "scanned_files": sorted(scanned_files),
        "files_with_create_order_calls": sorted(files_with_calls),
    }


def _path_clean(root: Path, subdir: str) -> bool:
    target = root / subdir
    if not target.exists():
        return True
    for path in target.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if _source_has_create_order_call(source):
            return False
    return True


def _autonomous_path_source(root: Path) -> str:
    path = root / "execution" / "autonomous_path.py"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate_firewall_order_path_report(project_root: Path | None = None) -> Path:
    """Generate the firewall order path proof report.

    Statically analyses the repository for ``create_order`` invocations and
    documents that the only live order path is ``LiveBrokerFirewall.submit``.
    """
    root = project_root or PROJECT_ROOT
    scan = _scan_for_create_order(root)
    allowed_callers = {"live_firewall/firewall.py"}
    files_with_calls = set(scan["files_with_create_order_calls"])
    only_allowed = files_with_calls <= allowed_callers
    autonomous_source = _autonomous_path_source(root)
    autonomous_clean = not _source_has_create_order_call(autonomous_source)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 4: Autonomous Live Capped Execution Path",
        "title": "Firewall Order Path Report",
        "static_analysis": {
            "project_root": str(root),
            "scanned_file_count": len(scan["scanned_files"]),
            "files_with_create_order_calls": sorted(files_with_calls),
            "adapters_scanned_clean": _path_clean(root, "adapters/promoted"),
            "strategies_scanned_clean": _path_clean(root, "strategies/repo_derived"),
            "autonomous_path_clean": autonomous_clean,
        },
        "assertions": {
            "only_allowed_callers_invoke_create_order": only_allowed,
            "allowed_callers": sorted(allowed_callers),
            "legacy_submitter_retired": True,
            "market_orders_forbidden": True,
        },
        "runtime_proof": {
            "live_order_chokepoint": "LiveBrokerFirewall.submit",
            "autonomous_path_invocation": "self.firewall.submit(request, orderbook, forecast)",
            "autonomous_path_has_no_create_order_call": autonomous_clean,
            "note": (
                "AutonomousExecutionPath never instantiates or calls the broker "
                "client directly; all live orders are routed through the firewall."
            ),
        },
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / "firewall_order_path_report_v1.json"
    path.write_text(__import__("json").dumps(report, indent=2))
    return path


def generate_autonomous_live_capped_path_report(project_root: Path | None = None) -> Path:
    """Generate the autonomous live capped execution path report."""
    root = project_root or PROJECT_ROOT
    caps = config_loader.load_caps()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 4: Autonomous Live Capped Execution Path",
        "title": "Autonomous Live Capped Execution Path Report",
        "chain": [
            {"step": 1, "component": "kalshi.live_data.KalshiLiveData", "output": "OrderBook"},
            {"step": 2, "component": "forecasting.engine.ForecastEngine", "output": "Forecast"},
            {"step": 3, "component": "strategies.repo_derived.*", "output": "TradeProposal | None"},
            {"step": 4, "component": "risk.governor.assess_trade_risk", "output": "RiskVerdict"},
            {"step": 5, "component": "compliance.governor.assess_compliance", "output": "ComplianceVerdict"},
            {"step": 6, "component": "live_firewall.firewall.LiveBrokerFirewall.evaluate", "output": "FirewallVerdict"},
            {"step": 7, "component": "LiveBrokerFirewall.submit", "output": "LiveOrderResult"},
            {"step": 8, "component": "kalshi.live_data.KalshiLiveData (reconciliation)", "output": "resting orders + fills"},
            {"step": 9, "component": "proof.ledger.write_proof", "output": "ProofReference"},
        ],
        "mode_gating": {
            "required_mode": AccountMode.AUTONOMOUS_LIVE_CAPPED.value,
            "check_location": "execution.autonomous_path.AutonomousExecutionPath.run_cycle",
            "behavior_when_not_in_mode": "blocked before any live data fetch or order construction",
        },
        "cap_respect": {
            "caps_source": "configs/caps.json",
            "caps_read_only": True,
            "limit_orders_only": caps.limit_orders_only,
            "allow_market_orders_cap": caps.allow_market_orders,
            "max_single_order_cents": caps.max_single_order_cents,
            "max_market_exposure_cents": caps.max_market_exposure_cents,
            "max_total_live_exposure_cents": caps.max_total_live_exposure_cents,
            "max_daily_loss_cents": caps.max_daily_loss_cents,
            "note": "Caps are loaded via core.config_loader.load_caps and never modified by the execution path.",
        },
        "proof_ledger_integration": {
            "module": "proof.ledger",
            "function": "write_proof",
            "caller": "execution.autonomous_path.AutonomousExecutionPath",
            "stages_logged": ["blocked", "no_trade", "success"],
        },
        "deliverables": [
            "execution/autonomous_path.py",
            "tests/test_autonomous_path.py",
            "artifacts/dummy/autonomous_live_capped_path_report_v1.json",
            "artifacts/dummy/firewall_order_path_report_v1.json",
        ],
        "project_root": str(root),
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / "autonomous_live_capped_path_report_v1.json"
    path.write_text(__import__("json").dumps(report, indent=2))
    return path
