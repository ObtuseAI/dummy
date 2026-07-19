"""The Dummy Tote native desktop application (PySide6).

A real native window -- sidebar navigation, live-refreshing tote panels, a
ranked bet board, an edge chart, per-vertical / LLM / health views, and switch
toggles that write configs/switches.json (the same control the CLI uses). It
reads only the runtime artifacts (via data.RepoData), so it runs standalone
and never blocks or contends the trading system.
"""
from __future__ import annotations

from typing import Callable

import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from desktop.dummy_tote import theme
from desktop.dummy_tote.data import KNOWN_LEAGUES, LLM_BACKENDS, RepoData, Snapshot

REFRESH_MS = 4000


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
    t.setSortingEnabled(True)
    return t


def _cell(text: str, color: str | None = None, align_right: bool = False) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem(text)
    if color:
        item.setForeground(QtGui.QColor(color))
    if align_right:
        item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    return item


def _pct(value) -> str:
    return f"{value * 100:.1f}%" if isinstance(value, (int, float)) else "—"


def _edge_color(edge) -> str:
    if not isinstance(edge, (int, float)):
        return theme.CHALK_DIM
    return theme.TURF if edge >= 0 else theme.CLAY


# ---- views -----------------------------------------------------------------

class OverviewView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(16)

        self.k_status, self.v_status, self.s_status = self._named_kpi("System")
        self.k_bankroll, self.v_bankroll, self.s_bankroll = self._named_kpi("Bankroll")
        self.k_picks, self.v_picks, self.s_picks = self._named_kpi("Ranked markets")
        self.k_edge, self.v_edge, self.s_edge = self._named_kpi("Top edge")
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
        self.picks = _table(["#", "matchup", "league", "pick", "prob", "edge"])
        picks_box.addWidget(self.picks)
        grid.addWidget(picks_card, 1, 2, 1, 2)
        grid.setRowStretch(1, 1)

    def _named_kpi(self, title):
        return _kpi(title)

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
            axis = self.plot.getAxis("left")
            axis.setTicks([[(i, str(p.get("matchup") or p.get("ticker", ""))[:14])
                            for i, p in enumerate(picks[::-1])]])
        _fill_picks(self.picks, snap.picks()[:14])


def _fill_picks(table: QtWidgets.QTableWidget, picks: list[dict]):
    table.setSortingEnabled(False)
    table.setRowCount(len(picks))
    for r, p in enumerate(picks):
        table.setItem(r, 0, _cell(str(p.get("rank", r + 1))))
        table.setItem(r, 1, _cell(str(p.get("matchup") or p.get("ticker", ""))[:28]))
        table.setItem(r, 2, _cell(str(p.get("league", ""))))
        pick = str(p.get("pick") or "—").upper()
        table.setItem(r, 3, _cell(pick, theme.TURF if pick == "YES" else theme.CLAY if pick == "NO" else theme.CHALK_DIM))
        table.setItem(r, 4, _cell(_pct(p.get("probability")), align_right=True))
        table.setItem(r, 5, _cell(_pct(p.get("edge")), _edge_color(p.get("edge")), align_right=True))
    table.setSortingEnabled(True)


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
        bar.addWidget(QtWidgets.QLabel("filter:"))
        bar.addWidget(self.filter)
        box.addLayout(bar)
        self.table = _table(["#", "matchup", "league", "type", "pick", "prob", "market", "edge", "tier"])
        box.addWidget(self.table)
        self._rows: list[dict] = []

    def update(self, snap: Snapshot):
        groups = snap.board.get("groups") or {}
        rows = []
        for league, bets in groups.items():
            if isinstance(bets, dict):
                for _bt, items in bets.items():
                    rows.extend(x for x in items if isinstance(x, dict))
        rows.sort(key=lambda x: abs(x.get("edge") or 0), reverse=True)
        self._rows = rows
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
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            self.table.setItem(r, 0, _cell(str(p.get("rank", r + 1))))
            self.table.setItem(r, 1, _cell(str(p.get("matchup") or p.get("ticker", ""))[:30]))
            self.table.setItem(r, 2, _cell(str(p.get("league", ""))))
            self.table.setItem(r, 3, _cell(str(p.get("bet_type", ""))))
            pick = str(p.get("pick") or "—").upper()
            self.table.setItem(r, 4, _cell(pick, theme.TURF if pick == "YES" else theme.CLAY if pick == "NO" else theme.CHALK_DIM))
            self.table.setItem(r, 5, _cell(_pct(p.get("probability")), align_right=True))
            self.table.setItem(r, 6, _cell(_pct(p.get("market_probability")), align_right=True))
            self.table.setItem(r, 7, _cell(_pct(p.get("edge")), _edge_color(p.get("edge")), align_right=True))
            self.table.setItem(r, 8, _cell(str(p.get("tier") or "—")))
        self.table.setSortingEnabled(True)


class KeyValueView(QtWidgets.QWidget):
    """A simple titled panel that renders key/value rows from a snapshot slice."""

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
        lab = _display(label, 15, theme.AMBER if main else theme.CHALK)
        h.addWidget(lab)
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


# ---- main window -----------------------------------------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, root: str | None = None):
        super().__init__()
        self.data = RepoData(root)
        self.setWindowTitle("Dummy Tote")
        self.resize(1360, 860)

        root_w = QtWidgets.QWidget()
        root_w.setObjectName("Root")
        self.setCentralWidget(root_w)
        outer = QtWidgets.QHBoxLayout(root_w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
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
        self._add_nav(sb, "Crypto", KeyValueView("Crypto paper twin", _crypto_rows))
        self._add_nav(sb, "LLM Debate", KeyValueView("LLM panel", _llm_rows))
        self._add_nav(sb, "vNext", KeyValueView("vNext shadow organisms", _vnext_rows))
        self._add_nav(sb, "Health", KeyValueView("System health", _health_rows))
        self._add_nav(sb, "Switches", SwitchesView(self.data))
        sb.addStretch(1)
        outer.addWidget(sidebar)

        # Right column: top bar + stack
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
        self.lamp = QtWidgets.QLabel("···")
        self.lamp.setObjectName("LampDead")
        self.updated = QtWidgets.QLabel("")
        self.updated.setObjectName("Muted")
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
        menu.addAction("Show", self.showNormal)
        menu.addAction("Quit", QtWidgets.QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QtWidgets.QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def refresh(self):
        snap = self.data.snapshot()
        alive = snap.alive()
        self.lamp.setText("LIVE" if alive else "STALE")
        self.lamp.setObjectName("LampLive" if alive else "LampDead")
        self.lamp.setStyle(self.lamp.style())   # re-polish for the object-name swap
        self.lamp.setStyleSheet(self.styleSheet())
        import time as _t
        self.updated.setText("updated " + _t.strftime("%H:%M:%S"))
        for view in self.views:
            try:
                view.update(snap)
            except Exception:
                pass


# ---- snapshot -> key/value extractors --------------------------------------

def _crypto_rows(snap: Snapshot):
    c = snap.crypto or {}
    return [
        ("status", str(c.get("status") or "—"), None),
        ("settled trades", str(c.get("settled") or c.get("n_settled") or "—"), None),
        ("net cents", str(c.get("net_cents") or "—"),
         theme.TURF if (c.get("net_cents") or 0) >= 0 else theme.CLAY),
        ("generated", str(c.get("generated_at") or c.get("at") or "—")[11:19], None),
    ]


def _llm_rows(snap: Snapshot):
    llm = snap.llm_state()
    rows = [("debate backends", "", None)]
    for b, on in llm.items():
        rows.append((f"  {b}", "ON" if on else "off", theme.TURF if on else theme.CHALK_DIM))
    budget = snap.budget or {}
    rows.append(("odds credits today", f"{budget.get('spent_today', '—')} spent", None))
    return rows


def _vnext_rows(snap: Snapshot):
    v = snap.vnext or {}
    errs = v.get("errors") or []
    return [
        ("episodes on ledger", str(v.get("episodes_on_ledger", 0)), theme.TURF if (v.get("episodes_on_ledger") or 0) > 0 else None),
        ("pending settlement", str(v.get("pending", "—")), None),
        ("issued last pass", str(v.get("issued", "—")), None),
        ("completed last pass", str(v.get("completed", "—")), None),
        ("errors", str(len(errs)), theme.CLAY if errs else theme.TURF),
        ("ledger", "busy" if v.get("ledger_busy") else "ok", theme.AMBER if v.get("ledger_busy") else theme.TURF),
    ]


def _health_rows(snap: Snapshot):
    heal = snap.heal or {}
    reach = heal.get("reachable") or []
    unreach = heal.get("unreachable") or []
    rows = [
        ("connectivity", "online" if snap.connectivity_ok() else "OFFLINE",
         theme.TURF if snap.connectivity_ok() else theme.CLAY),
        ("venues reachable", f"{len(reach)}/{len(reach) + len(unreach)}", None),
        ("restarted (last heal)", ", ".join(heal.get("restarted") or []) or "none", None),
        ("heartbeat", "alive" if snap.alive() else "stale", theme.TURF if snap.alive() else theme.CLAY),
        ("stale artifacts", ", ".join(snap.stale()) or "none",
         theme.CLAY if snap.stale() else theme.TURF),
    ]
    return rows


def run(root: str | None = None) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setStyleSheet(theme.stylesheet())
    window = MainWindow(root)
    window.show()
    return app.exec()
