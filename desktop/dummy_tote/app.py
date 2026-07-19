"""The Dummy Tote native desktop application (PySide6).

A real native window -- sidebar navigation, live-refreshing tote panels, and a
view for every process worth evaluating: the ranked bet board, live
mispricing, crypto throughput, promotion readiness, the self-improvement plan,
the model panel, health, and switch controls. Reads only the runtime artifacts
(via data.RepoData), so it runs standalone and never contends the trading
system.
"""
from __future__ import annotations

from typing import Callable

import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from desktop.dummy_tote import theme
from desktop.dummy_tote.data import KNOWN_LEAGUES, LLM_BACKENDS, RepoData, Snapshot

REFRESH_MS = 4000
# A cell is text, or (text, colour), or (text, colour, align_right).
Cell = object


# ---- small widget helpers --------------------------------------------------

def _display(text: str, size: int, color: str, spacing: int = 1) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    lab.setStyleSheet(
        f'font-family:"{theme.DISPLAY_FONT}";font-size:{size}px;color:{color};'
        f"letter-spacing:{spacing}px;")
    return lab


def _card(title: str) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    frame = QtWidgets.QFrame()
    frame.setObjectName("Card")
    outer = QtWidgets.QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(8)
    label = QtWidgets.QLabel(title.upper())
    label.setObjectName("CardTitle")
    outer.addWidget(label)
    return frame, outer


def _kpi(title: str) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel, QtWidgets.QLabel]:
    frame, box = _card(title)
    value = QtWidgets.QLabel("—")
    value.setObjectName("KpiValue")
    sub = QtWidgets.QLabel("")
    sub.setObjectName("KpiSub")
    box.addWidget(value)
    box.addWidget(sub)
    box.addStretch(1)
    return frame, value, sub


def _table(headers: list[str]) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    t.setShowGrid(True)
    t.horizontalHeader().setStretchLastSection(True)
    # Rows arrive pre-ordered by the extractor (by edge / eligibility / a
    # meaningful funnel order), so auto-sort stays OFF -- it would scramble a
    # metric/value table.
    t.setSortingEnabled(False)
    return t


def _cell(text: str, color: str | None = None, align_right: bool = False) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem(text)
    if color:
        item.setForeground(QtGui.QColor(color))
    if align_right:
        item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    return item


def _to_item(cell: Cell) -> QtWidgets.QTableWidgetItem:
    if isinstance(cell, tuple):
        text = str(cell[0])
        color = cell[1] if len(cell) > 1 else None
        align = cell[2] if len(cell) > 2 else False
        return _cell(text, color, align)
    return _cell(str(cell))


def _fill(table: QtWidgets.QTableWidget, rows: list[list[Cell]]):
    was_sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            table.setItem(r, c, _to_item(cell))
    table.setSortingEnabled(was_sorting)


def _pct(value) -> str:
    return f"{value * 100:.1f}%" if isinstance(value, (int, float)) else "—"


def _num(value) -> str:
    return f"{value:,}" if isinstance(value, (int, float)) else "—"


def _label(row: dict) -> str:
    """How the market reads on Kalshi -- the human title, not the raw token."""
    return str(row.get("title") or row.get("matchup") or row.get("ticker") or "")


def _edge_color(edge) -> str:
    if not isinstance(edge, (int, float)):
        return theme.CHALK_DIM
    return theme.TURF if edge >= 0 else theme.CLAY


def _pick_color(pick: str) -> str:
    return theme.TURF if pick == "YES" else theme.CLAY if pick == "NO" else theme.CHALK_DIM


# ---- generic table view ----------------------------------------------------

class TableView(QtWidgets.QWidget):
    """A titled panel that renders rows from a snapshot extractor. The extractor
    returns (headers, rows); rows are lists of cells."""

    def __init__(self, title: str, extract: Callable[[Snapshot], tuple[list[str], list[list[Cell]]]],
                 note: str = ""):
        super().__init__()
        self._extract = extract
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(20, 20, 20, 20)
        box.setSpacing(10)
        box.addWidget(_display(title.upper(), 20, theme.CHALK))
        if note:
            n = QtWidgets.QLabel(note)
            n.setObjectName("Muted")
            box.addWidget(n)
        self.table = _table(["", ""])
        box.addWidget(self.table)
        self._headers: list[str] = []

    def update(self, snap: Snapshot):
        headers, rows = self._extract(snap)
        if headers != self._headers:
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            self._headers = headers
        _fill(self.table, rows)


class KeyValueView(QtWidgets.QWidget):
    """A titled panel of key/value rows (for compact summaries)."""

    def __init__(self, title: str, extract: Callable[[Snapshot], list[tuple[str, str, str]]]):
        super().__init__()
        self._extract = extract
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(20, 20, 20, 20)
        card, self._box = _card(title)
        box.addWidget(_display(title.upper(), 20, theme.CHALK))
        box.addWidget(card)
        box.addStretch(1)
        self._rows_layout = QtWidgets.QGridLayout()
        self._box.addLayout(self._rows_layout)

    def update(self, snap: Snapshot):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for r, (key, value, color) in enumerate(self._extract(snap)):
            k = QtWidgets.QLabel(key)
            k.setObjectName("Muted")
            v = _display(str(value), 15, color or theme.CHALK)
            self._rows_layout.addWidget(k, r, 0)
            self._rows_layout.addWidget(v, r, 1, QtCore.Qt.AlignRight)


# ---- overview --------------------------------------------------------------

class OverviewView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(16)
        self.k_status, self.v_status, self.s_status = _kpi("System")
        self.k_bankroll, self.v_bankroll, self.s_bankroll = _kpi("Bankroll")
        self.k_picks, self.v_picks, self.s_picks = _kpi("Ranked markets")
        self.k_edge, self.v_edge, self.s_edge = _kpi("Top edge")
        for col, frame in enumerate((self.k_status, self.k_bankroll, self.k_picks, self.k_edge)):
            grid.addWidget(frame, 0, col)

        chart_card, chart_box = _card("Top edges")
        self.plot = pg.PlotWidget()
        self.plot.setBackground(theme.SLAT)
        self.plot.showGrid(x=True, y=False, alpha=0.15)
        self.plot.getAxis("left").setTextPen(theme.CHALK_DIM)
        self.plot.getAxis("bottom").setTextPen(theme.CHALK_DIM)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(False, False)
        chart_box.addWidget(self.plot)
        grid.addWidget(chart_card, 1, 0, 1, 2)

        picks_card, picks_box = _card("Top picks")
        self.picks = _table(["#", "market", "league", "pick", "prob", "edge"])
        picks_box.addWidget(self.picks)
        grid.addWidget(picks_card, 1, 2, 1, 2)
        grid.setRowStretch(1, 1)

    def update(self, snap: Snapshot):
        alive = snap.alive()
        self.v_status.setText("ALIVE" if alive else "STALE")
        self.v_status.setStyleSheet(
            f'font-family:"{theme.DISPLAY_FONT}";font-size:34px;'
            f'color:{theme.AMBER if alive else theme.CLAY};')
        conn = "online" if snap.connectivity_ok() else "OFFLINE"
        self.s_status.setText(f"{snap.mode()} · {conn} · cycle {snap.last_cycle()[11:19] or '—'}")

        risk = snap.risk or {}
        bankroll = risk.get("bankroll_cents")
        self.v_bankroll.setText(f"${bankroll / 100:,.0f}" if isinstance(bankroll, (int, float)) else "—")
        self.s_bankroll.setText(f"stage {risk.get('stage', '—')}")

        self.v_picks.setText(str(snap.pick_count()))
        stale = snap.stale()
        self.s_picks.setText("all fresh" if not stale else f"stale: {', '.join(stale)[:40]}")

        te = snap.top_edge()
        self.v_edge.setText(_pct(te) if te is not None else "—")
        self.s_edge.setText("fused vs market")

        picks = snap.picks()[:12]
        self.plot.clear()
        if picks:
            edges = [abs(p.get("edge") or 0) * 100 for p in picks][::-1]
            ys = list(range(len(edges)))
            colors = [_edge_color(p.get("edge")) for p in picks][::-1]
            bars = pg.BarGraphItem(x0=0, y=ys, height=0.6, width=edges,
                                   brushes=[pg.mkBrush(c) for c in colors])
            self.plot.addItem(bars)
            self.plot.getAxis("left").setTicks(
                [[(i, _label(p)[:16]) for i, p in enumerate(picks[::-1])]])

        rows = []
        for r, p in enumerate(snap.picks()[:14]):
            pick = str(p.get("pick") or "—").upper()
            rows.append([str(p.get("rank", r + 1)), _label(p)[:34], str(p.get("league", "")),
                         (pick, _pick_color(pick)),
                         (_pct(p.get("probability")), None, True),
                         (_pct(p.get("edge")), _edge_color(p.get("edge")), True)])
        _fill(self.picks, rows)


class BetBoardView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(20, 20, 20, 20)
        box.setSpacing(12)
        bar = QtWidgets.QHBoxLayout()
        self.filter = QtWidgets.QComboBox()
        self.filter.addItem("all leagues")
        self.filter.currentTextChanged.connect(lambda _: self._render())
        bar.addWidget(_display("BET BOARD", 20, theme.CHALK))
        bar.addStretch(1)
        self.count = QtWidgets.QLabel("")
        self.count.setObjectName("Muted")
        bar.addWidget(self.count)
        bar.addSpacing(14)
        bar.addWidget(QtWidgets.QLabel("filter:"))
        bar.addWidget(self.filter)
        box.addLayout(bar)
        self.table = _table(["#", "market (as on Kalshi)", "league", "type", "pick", "prob", "market", "edge", "tier"])
        box.addWidget(self.table)
        self._rows: list[dict] = []

    def update(self, snap: Snapshot):
        groups = snap.board.get("groups") or {}
        rows = []
        for _league, bets in groups.items():
            if isinstance(bets, dict):
                for _bt, items in bets.items():
                    rows.extend(x for x in items if isinstance(x, dict))
        rows.sort(key=lambda x: abs(x.get("edge") or 0), reverse=True)
        self._rows = rows
        self.count.setText(f"{len(rows)} markets priced")
        leagues = sorted({str(r.get("league", "")) for r in rows if r.get("league")})
        current = self.filter.currentText()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("all leagues")
        self.filter.addItems(leagues)
        idx = self.filter.findText(current)
        self.filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter.blockSignals(False)
        self._render()

    def _render(self):
        chosen = self.filter.currentText()
        rows = [r for r in self._rows if chosen == "all leagues" or str(r.get("league")) == chosen]
        out = []
        for r, p in enumerate(rows):
            pick = str(p.get("pick") or "—").upper()
            out.append([str(p.get("rank", r + 1)), _label(p)[:44], str(p.get("league", "")),
                        str(p.get("bet_type", "")), (pick, _pick_color(pick)),
                        (_pct(p.get("probability")), None, True),
                        (_pct(p.get("market_probability")), None, True),
                        (_pct(p.get("edge")), _edge_color(p.get("edge")), True),
                        str(p.get("tier") or "—")])
        _fill(self.table, out)


class SwitchesView(QtWidgets.QWidget):
    def __init__(self, data: RepoData):
        super().__init__()
        self._data = data
        self._buttons: dict[tuple[str, str], QtWidgets.QPushButton] = {}
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(20, 20, 20, 20)
        box.setSpacing(10)
        box.addWidget(_display("CONTROL SWITCHES", 20, theme.CHALK))
        note = QtWidgets.QLabel("Toggles write configs/switches.json — the tasks pick them up on the next fire.")
        note.setObjectName("Muted")
        box.addWidget(note)
        box.addWidget(self._row("MAIN (kill switch)", "main", "", main=True))
        box.addWidget(self._row("crypto", "crypto", ""))
        box.addWidget(self._row("sports", "sports", ""))
        for lg in KNOWN_LEAGUES:
            box.addWidget(self._row(f"  · {lg}", "league", lg))
        box.addSpacing(8)
        for backend in LLM_BACKENDS:
            box.addWidget(self._row(f"llm · {backend}", "llm", backend))
        box.addStretch(1)

    def _row(self, label: str, domain: str, key: str, main: bool = False) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(_display(label, 15, theme.AMBER if main else theme.CHALK))
        h.addStretch(1)
        btn = QtWidgets.QPushButton("—")
        btn.setObjectName("ToggleMain" if main else "Toggle")
        btn.setCheckable(True)
        btn.clicked.connect(lambda checked, d=domain, k=key: self._flip(d, k, checked))
        self._buttons[(domain, key)] = btn
        h.addWidget(btn)
        return w

    def _flip(self, domain: str, key: str, checked: bool):
        try:
            self._data.set_switch(domain, checked, key or None)
        except Exception:
            pass
        self._buttons[(domain, key)].setText("ON" if checked else "OFF")

    def update(self, snap: Snapshot):
        sw = snap.switches or {}

        def state(domain, key):
            if domain in ("main", "crypto", "sports"):
                return bool(sw.get(domain, True))
            if domain == "league":
                return bool((sw.get("leagues") or {}).get(key, True))
            if domain == "llm":
                return bool((sw.get("llm") or {}).get(key, key == "openrouter"))
            return False
        for (domain, key), btn in self._buttons.items():
            on = state(domain, key)
            btn.blockSignals(True)
            btn.setChecked(on)
            btn.setText("ON" if on else "OFF")
            btn.blockSignals(False)


# ---- snapshot -> table extractors ------------------------------------------

def _mispricing(snap: Snapshot):
    m = snap.mispricing or {}
    short = [x for x in (m.get("shortlist") or []) if isinstance(x, dict)]
    short.sort(key=lambda x: abs(x.get("edge") or 0), reverse=True)
    headers = ["ticker", "side", "edge", "model", "book", "agreement", "conf", "tier"]
    rows = []
    for p in short[:60]:
        rows.append([
            str(p.get("ticker", ""))[:26], str(p.get("side", "")),
            (_pct(p.get("edge")), _edge_color(p.get("edge")), True),
            (_pct(p.get("model_prob")), None, True),
            (_pct(p.get("book_prob")), None, True),
            str(p.get("agreement", "")), str(p.get("confidence", "")),
            str(p.get("conviction_tier") or "—")])
    return headers, rows


def _readiness(snap: Snapshot):
    r = snap.readiness or {}
    scopes = [s for s in (r.get("scopes") or []) if isinstance(s, dict)]
    # Closest to promotion first: eligible, then fewest days to eligibility.
    scopes.sort(key=lambda s: (not s.get("eligible"), s.get("days_to_eligibility") or 1e9))
    headers = ["scope", "clusters", "mean edge", "edge ci95", "days→elig", "status"]
    rows = []
    for s in scopes[:80]:
        elig = s.get("eligible")
        degrading = s.get("degrading")
        status = "ELIGIBLE" if elig else ("degrading" if degrading else "accruing")
        ci = s.get("edge_ci95")
        ci_txt = (f"{ci[0]:+.3f}/{ci[1]:+.3f}" if isinstance(ci, (list, tuple)) and len(ci) == 2 else "—")
        rows.append([
            str(s.get("scope", ""))[:40], str(s.get("n_clusters", "—")),
            (f"{s.get('mean_edge'):+.4f}" if isinstance(s.get("mean_edge"), (int, float)) else "—",
             _edge_color(s.get("mean_edge")), True),
            (ci_txt, None, True),
            str(s.get("days_to_eligibility", "—")),
            (status, theme.TURF if elig else theme.CLAY if degrading else theme.CHALK_DIM)])
    return headers, rows


def _crypto(snap: Snapshot):
    c = snap.crypto or {}
    tp = (c.get("throughput") or {}).get("classes") or {}
    headers = ["metric", "value"]
    rows = [
        ["status", str(c.get("status") or "—")],
        ["mode", str(c.get("paper_mode") or "—")],
        ["markets seen", (_num(c.get("markets_seen")), None, True)],
        ["TRADED (paper)", (_num(tp.get("traded")), theme.TURF, True)],
        ["policy-rejected (discipline)", (_num(tp.get("policy_rejected")), theme.CHALK_DIM, True)],
        ["no listed market", (_num(tp.get("no_listed_market")), theme.CHALK_DIM, True)],
        ["no two-sided book", (_num(tp.get("no_two_sided_book")), theme.CHALK_DIM, True)],
        ["trades opened (cycle)", (_num(c.get("trades_opened")), None, True)],
        ["forced-crypto trades", (_num(c.get("forced_crypto_trades_recorded")), None, True)],
        ["forced-crypto settlements", (_num(c.get("forced_crypto_settlements_recorded")), None, True)],
        ["candidate forecasts", (_num(c.get("target_candidate_forecasts_recorded")), None, True)],
        ["candidate settlements", (_num(c.get("target_candidate_settlements_recorded")), None, True)],
        ["observations written", (_num(c.get("observations_written")), None, True)],
        ["lanes", ", ".join((c.get("lanes") or {}).keys()) or "—"],
        ["completed", str(c.get("completed_at") or "—")[11:19]],
    ]
    return headers, rows


def _selfimprove(snap: Snapshot):
    plan = snap.plan or {}
    items = [i for i in (plan.get("items") or []) if isinstance(i, dict)]
    headers = ["kind", "target", "severity", "next / detail"]
    rows = []
    for it in items[:60]:
        sev = it.get("severity")
        rows.append([
            str(it.get("kind", ""))[:24], str(it.get("target", ""))[:30],
            (str(sev), theme.CLAY if isinstance(sev, (int, float)) and sev >= 8 else theme.CHALK_DIM, True),
            str(it.get("next") or it.get("owner") or "")[:60]])
    if not rows:
        loops = plan.get("closed_loops_active") or []
        rows = [["closed loop", str(x)[:60], "", "active"] for x in loops]
    return headers, rows


def _clv_rows(snap: Snapshot):
    scopes = (snap.clv or {}).get("scopes") or {}
    headers = ["scope", "entries", "clusters", "clv bps", "ci95 lower"]
    rows = []
    for name, s in scopes.items():
        if not isinstance(s, dict):
            continue
        mean = s.get("clv_bps_mean")
        rows.append([
            str(name)[:34], str(s.get("n_entries", "—")), str(s.get("n_event_clusters", "—")),
            (f"{mean:.1f}" if isinstance(mean, (int, float)) else "—",
             theme.TURF if isinstance(mean, (int, float)) and mean >= 0 else theme.CLAY, True),
            (f"{s.get('clv_bps_ci95_lower'):.1f}" if isinstance(s.get("clv_bps_ci95_lower"), (int, float)) else "—", None, True)])
    return headers, rows


# ---- summary (key/value) extractors ----------------------------------------

def _models_rows(snap: Snapshot):
    llm = snap.llm_state()
    v = snap.vnext or {}
    budget = snap.budget or {}
    rows = [("LLM debate backends", "", None)]
    for b, on in llm.items():
        rows.append((f"  {b}", "ON" if on else "off", theme.TURF if on else theme.CHALK_DIM))
    rows += [
        ("", "", None),
        ("vNext episodes on ledger", str(v.get("episodes_on_ledger", 0)),
         theme.TURF if (v.get("episodes_on_ledger") or 0) > 0 else None),
        ("vNext pending", str(v.get("pending", "—")), None),
        ("vNext issued last pass", str(v.get("issued", "—")), None),
        ("vNext errors", str(len(v.get("errors") or [])),
         theme.CLAY if (v.get("errors") or []) else theme.TURF),
        ("", "", None),
        ("odds credits spent today", str(budget.get("spent_today", "—")), None),
        ("odds daily cap", str(budget.get("daily_credits", "—")), None),
    ]
    return rows


def _promotion_rows(snap: Snapshot):
    p = snap.promotion or {}
    r = snap.readiness or {}
    cands = r.get("promotion_candidates") or []
    return [
        ("promotion ladder", str(p.get("status") or "—"), theme.TURF if p.get("status") == "OK" else theme.CLAY),
        ("eligible scopes", str(p.get("eligible_scopes", "—")), None),
        ("scopes evaluated", str(p.get("scopes_evaluated", "—")), None),
        ("promoted (run)", str(len(p.get("promoted") or [])), None),
        ("demoted (run)", str(len(p.get("demoted") or [])), None),
        ("live authority", str(p.get("live_trading_authority") or "—")[:36], theme.AMBER),
        ("", "", None),
        ("readiness candidates", str(len(cands)), theme.TURF if cands else theme.CHALK_DIM),
        *[(f"  · {str(c)[:38]}", "near", theme.AMBER) for c in cands[:5]],
    ]


def _health_rows(snap: Snapshot):
    heal = snap.heal or {}
    reach = heal.get("reachable") or []
    unreach = heal.get("unreachable") or []
    return [
        ("connectivity", "online" if snap.connectivity_ok() else "OFFLINE",
         theme.TURF if snap.connectivity_ok() else theme.CLAY),
        ("venues reachable", f"{len(reach)}/{len(reach) + len(unreach)}", None),
        ("restarted (last heal)", ", ".join(heal.get("restarted") or []) or "none", None),
        ("heartbeat", "alive" if snap.alive() else "stale", theme.TURF if snap.alive() else theme.CLAY),
        ("last cycle", snap.last_cycle()[11:19] or "—", None),
        ("stale artifacts", ", ".join(snap.stale()) or "none",
         theme.CLAY if snap.stale() else theme.TURF),
    ]


# ---- main window -----------------------------------------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, root: str | None = None):
        super().__init__()
        self.data = RepoData(root)
        self.setWindowTitle("Dummy Tote")
        self.resize(1420, 880)

        root_w = QtWidgets.QWidget()
        root_w.setObjectName("Root")
        self.setCentralWidget(root_w)
        outer = QtWidgets.QHBoxLayout(root_w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QtWidgets.QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        sb = QtWidgets.QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)
        brand = QtWidgets.QLabel("DUMMY TOTE")
        brand.setObjectName("Brand")
        sub = QtWidgets.QLabel("EVIDENCE BOARD")
        sub.setObjectName("BrandSub")
        sb.addWidget(brand)
        sb.addWidget(sub)

        self.stack = QtWidgets.QStackedWidget()
        self.views: list = []
        self._nav_buttons: list[QtWidgets.QPushButton] = []
        self._add_nav(sb, "Overview", OverviewView())
        self._add_nav(sb, "Bet Board", BetBoardView())
        self._add_nav(sb, "Mispricing", TableView(
            "Live mispricing", _mispricing,
            "Model vs de-vigged book vs price. Challenger/paper evidence — never auto-staked."))
        self._add_nav(sb, "Crypto", TableView("Crypto paper twin", _crypto,
            "Throughput funnel: TRADED are paper trades; policy-rejected is discipline."))
        self._add_nav(sb, "Readiness", TableView(
            "Promotion readiness", _readiness,
            "Every challenger scope, closest to promotion first. Promotion to capital is operator-only."))
        self._add_nav(sb, "Self-Improve", TableView(
            "Self-improvement plan", _selfimprove,
            "The machine's own ranked repair list from the nightly chain."))
        self._add_nav(sb, "CLV", TableView("Closing-line value", _clv_rows,
            "Cluster-level CLV evidence consumed by the promotion ladder."))
        self._add_nav(sb, "Promotion", KeyValueView("Promotion ladder", _promotion_rows))
        self._add_nav(sb, "Models", KeyValueView("Models & LLM", _models_rows))
        self._add_nav(sb, "Health", KeyValueView("System health", _health_rows))
        self._add_nav(sb, "Switches", SwitchesView(self.data))
        sb.addStretch(1)
        outer.addWidget(sidebar)

        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        top = QtWidgets.QWidget()
        top.setObjectName("TopBar")
        top.setFixedHeight(56)
        th = QtWidgets.QHBoxLayout(top)
        th.setContentsMargins(20, 0, 20, 0)
        self.title = QtWidgets.QLabel("Overview")
        self.title.setObjectName("TopTitle")
        th.addWidget(self.title)
        th.addStretch(1)
        self.updated = QtWidgets.QLabel("")
        self.updated.setObjectName("Muted")
        self.lamp = QtWidgets.QLabel("···")
        self.lamp.setObjectName("LampDead")
        th.addWidget(self.updated)
        th.addSpacing(14)
        th.addWidget(self.lamp)
        right.addWidget(top)
        right.addWidget(self.stack, 1)
        outer.addLayout(right, 1)

        self._nav_buttons[0].setChecked(True)
        self._tray()
        self.refresh()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)

    def _add_nav(self, layout, name, view):
        btn = QtWidgets.QPushButton(name)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        idx = len(self.views)
        btn.clicked.connect(lambda _=False, i=idx, n=name: self._select(i, n))
        layout.addWidget(btn)
        self._nav_buttons.append(btn)
        self.stack.addWidget(view)
        self.views.append(view)

    def _select(self, index: int, name: str):
        self.stack.setCurrentIndex(index)
        self.title.setText(name)
        for i, b in enumerate(self._nav_buttons):
            b.setChecked(i == index)

    def _tray(self):
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_DesktopIcon)
        self.tray = QtWidgets.QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Dummy Tote")
        menu = QtWidgets.QMenu()
        menu.addAction("Open App", self._open_app)
        menu.addAction("Open Dashboard", self._open_dashboard)
        menu.addSeparator()
        menu.addAction("Exit", QtWidgets.QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._open_app() if r in (
                QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()
        # Wave-54: native toasts on opened/settled bets. Seed silently so a first
        # run never blasts historical settlements, then poll the outcomes table.
        from desktop.dummy_tote import bet_notify

        self._bet_notify = bet_notify
        try:
            bet_notify.seed_silently()
            self._bet_last_id = bet_notify.read_state()
        except Exception:
            self._bet_last_id = 0
        self._bet_timer = QtCore.QTimer(self)
        self._bet_timer.timeout.connect(self._check_bet_events)
        self._bet_timer.start(30000)

    def _open_app(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _open_dashboard(self):
        import os
        import subprocess

        url = os.environ.get("DUMMY_DASHBOARD_URL") or "http://127.0.0.1:8787/"
        edge = os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                            "Microsoft", "Edge", "Application", "msedge.exe")
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            if os.path.exists(edge):
                subprocess.Popen([edge, f"--app={url}"], creationflags=no_window)
            else:
                os.startfile(url)  # noqa: S606 -- open the local dashboard URL
        except OSError:
            try:
                os.startfile(url)  # noqa: S606
            except OSError:
                pass

    def _check_bet_events(self):
        try:
            events, new_last = self._bet_notify.collect_events(self._bet_last_id)
            if new_last <= self._bet_last_id:
                return
            for ev in events[:6]:
                level = (QtWidgets.QSystemTrayIcon.Warning if ev["warning"]
                         else QtWidgets.QSystemTrayIcon.Information)
                self.tray.showMessage(ev["title"], ev["body"], level, 6000)
            extra = len(events) - min(len(events), 6)
            if extra > 0:
                self.tray.showMessage("Dummy", f"+{extra} more bet events",
                                      QtWidgets.QSystemTrayIcon.Information, 5000)
            self._bet_last_id = new_last
            self._bet_notify.write_state(new_last)
        except Exception:
            pass

    def refresh(self):
        snap = self.data.snapshot()
        alive = snap.alive()
        self.lamp.setText("LIVE" if alive else "STALE")
        self.lamp.setObjectName("LampLive" if alive else "LampDead")
        self.lamp.setStyleSheet(self.styleSheet())
        import time as _t
        self.updated.setText("updated " + _t.strftime("%H:%M:%S"))
        for view in self.views:
            try:
                view.update(snap)
            except Exception:
                pass


def run(root: str | None = None) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setStyleSheet(theme.stylesheet())
    window = MainWindow(root)
    window.show()
    return app.exec()
