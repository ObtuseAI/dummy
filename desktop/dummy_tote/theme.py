"""The Dummy Tote visual identity -- a racetrack tote / bookmaker's board.

Palette and Qt stylesheet (QSS) applied to native widgets, so the app looks
like the totalizator (the same thesis as the web dashboard) but is real native
chrome: pitch-green board, felt panels, chalk numerals, amber lamps, turf/clay
for winners/losers, brass hairlines. Windows-native display face (Bahnschrift)
with a Segoe body, so nothing is downloaded.
"""
from __future__ import annotations

# Palette -----------------------------------------------------------------
BOARD = "#131E17"        # deepest board back
FELT = "#18271D"         # panel felt
FELT_HI = "#1E3325"      # raised felt / hover
SLAT = "#0F1712"         # engraved slat / inset
CHALK = "#E9E2CE"        # primary numerals
CHALK_DIM = "#9BAE9A"    # secondary
BRASS = "#6E6248"        # hairline rules
AMBER = "#F2B63C"        # live lamp / accent
AMBER_DIM = "#8A6B24"
TURF = "#7FAF7A"         # positive / on
CLAY = "#C75F49"         # negative / off / alarm
INK = "#0A0F0C"          # deepest ink

DISPLAY_FONT = "Bahnschrift SemiCondensed"
BODY_FONT = "Segoe UI"
MONO_FONT = "Cascadia Mono"


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: {BOARD};
        color: {CHALK};
        font-family: "{BODY_FONT}";
        font-size: 13px;
    }}
    QMainWindow, #Root {{ background: {BOARD}; }}

    /* Sidebar navigation */
    #Sidebar {{ background: {SLAT}; border-right: 1px solid {BRASS}; }}
    #Brand {{
        font-family: "{DISPLAY_FONT}"; font-size: 22px; font-weight: 600;
        color: {AMBER}; letter-spacing: 2px; padding: 18px 18px 6px 18px;
    }}
    #BrandSub {{ color: {CHALK_DIM}; padding: 0 18px 14px 18px; font-size: 11px; letter-spacing: 3px; }}
    QPushButton#NavButton {{
        text-align: left; padding: 12px 18px; border: none; border-radius: 0;
        background: transparent; color: {CHALK_DIM};
        font-family: "{DISPLAY_FONT}"; font-size: 15px; letter-spacing: 1px;
    }}
    QPushButton#NavButton:hover {{ background: {FELT}; color: {CHALK}; }}
    QPushButton#NavButton:checked {{
        background: {FELT_HI}; color: {AMBER};
        border-left: 3px solid {AMBER};
    }}

    /* Top bar */
    #TopBar {{ background: {SLAT}; border-bottom: 1px solid {BRASS}; }}
    #TopTitle {{ font-family: "{DISPLAY_FONT}"; font-size: 20px; letter-spacing: 1px; color: {CHALK}; }}

    /* Cards / panels -- engraved felt slats, no rounded corners */
    QFrame#Card {{
        background: {FELT}; border: 1px solid {BRASS};
    }}
    QLabel#CardTitle {{
        font-family: "{DISPLAY_FONT}"; font-size: 13px; letter-spacing: 2px;
        color: {CHALK_DIM}; text-transform: uppercase;
    }}
    QLabel#KpiValue {{ font-family: "{DISPLAY_FONT}"; font-size: 34px; color: {CHALK}; }}
    QLabel#KpiValueAmber {{ font-family: "{DISPLAY_FONT}"; font-size: 34px; color: {AMBER}; }}
    QLabel#KpiSub {{ color: {CHALK_DIM}; font-size: 11px; letter-spacing: 1px; }}
    QLabel#Muted {{ color: {CHALK_DIM}; }}

    /* Lamps / pills */
    QLabel#LampLive {{
        background: {AMBER}; color: {INK}; padding: 3px 12px;
        font-family: "{DISPLAY_FONT}"; letter-spacing: 2px; font-weight: 600;
    }}
    QLabel#LampDead {{
        background: {CLAY}; color: {INK}; padding: 3px 12px;
        font-family: "{DISPLAY_FONT}"; letter-spacing: 2px; font-weight: 600;
    }}

    /* Tables -- the tote board */
    QTableWidget {{
        background: {SLAT}; gridline-color: {BRASS}; border: 1px solid {BRASS};
        selection-background-color: {FELT_HI}; selection-color: {AMBER};
        font-family: "{MONO_FONT}"; font-size: 12px;
    }}
    QHeaderView::section {{
        background: {BOARD}; color: {CHALK_DIM}; border: none;
        border-bottom: 1px solid {BRASS}; padding: 6px 8px;
        font-family: "{DISPLAY_FONT}"; letter-spacing: 1px;
    }}
    QTableWidget::item {{ padding: 4px 8px; }}

    /* Toggle buttons (switches) */
    QPushButton#Toggle {{
        border: 1px solid {BRASS}; padding: 6px 16px; min-width: 54px;
        font-family: "{DISPLAY_FONT}"; letter-spacing: 1px;
        background: {SLAT}; color: {CHALK_DIM};
    }}
    QPushButton#Toggle:checked {{ background: {TURF}; color: {INK}; border: 1px solid {TURF}; }}
    QPushButton#ToggleMain:checked {{ background: {AMBER}; color: {INK}; border: 1px solid {AMBER}; }}

    /* Scrollbars */
    QScrollBar:vertical {{ background: {BOARD}; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {BRASS}; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QToolTip {{ background: {INK}; color: {CHALK}; border: 1px solid {BRASS}; }}
    """
