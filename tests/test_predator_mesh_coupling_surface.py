"""Wave-85: pin how much of the 295-snapshot archive LIVE code depends on.

``predator_mesh`` is 311 directories and 730 tracked files -- roughly a quarter
of all tracked Python -- and every external audit so far has proposed the same
remedy: freeze one ``vNext`` and move the rest to git tags or ``archive/``.

Measured, that move is far more expensive than it looks, which is why Wave-85
did NOT attempt it:

    616  files under archive/ reference predator_mesh
    452  test files reference predator_mesh
    295  distinct predator_mesh.vNN modules are imported from outside the tree

A mass move rewrites imports in ~1,068 files, and the snapshots are required to
stay byte-identical (295 of them import ``risk/governor.py``, which is exactly
why that module could not be renamed). The dashboard also lazy-mounts the
archived routers, and tests/test_vnext_final_audit.py pins all 295 archived
React dashboards as preserved.

What IS cheap is stopping the coupling from GROWING. Live production code --
everything outside tests/ and archive/ -- touches a tiny, enumerable surface:
three snapshot versions and two shared packages. This test pins that surface.

If this test fails because you added a NEW live dependency on a snapshot
version, that is the point: prefer promoting the code you need out of the
snapshot into a maintained module, so the archive stays archive. Widening the
allow-list should be a deliberate, commented decision.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories that are the LIVE surface: not tests, not the archive tree, and
# not predator_mesh itself.
LIVE_DIRS = (
    "autonomy", "core", "dashboard", "dummy", "execution", "forecasting",
    "kalshi", "live_firewall", "model_router", "risk", "scripts", "tools",
)

# Every predator_mesh import live code is currently allowed to make.
ALLOWED_LIVE_IMPORTS = {
    # Shared broker/gate packages, not version snapshots.
    "predator_mesh.brokers",
    "predator_mesh.staged_gate_common",
    # The only three archived version snapshots live code still reads, all
    # report builders reached through scripts/run_dummy_*_report.py.
    "predator_mesh.v207",
    "predator_mesh.v208",
    "predator_mesh.v213",
}

_IMPORT = re.compile(r"\bpredator_mesh(?:\.[A-Za-z_][A-Za-z_0-9]*)*")


def _live_imports() -> dict[str, set[str]]:
    """Map each live file to the predator_mesh roots it references."""
    found: dict[str, set[str]] = {}
    for directory in LIVE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in _IMPORT.findall(text):
                parts = match.split(".")
                # Normalise to the first meaningful level: predator_mesh.<x>.
                root = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
                if root == "predator_mesh":
                    continue          # bare package reference, not a snapshot
                found.setdefault(str(path.relative_to(ROOT)), set()).add(root)
    return found


def test_live_code_touches_only_the_pinned_predator_mesh_surface():
    offenders: dict[str, set[str]] = {}
    for file, roots in _live_imports().items():
        extra = roots - ALLOWED_LIVE_IMPORTS
        if extra:
            offenders[file] = extra
    assert not offenders, (
        "new live dependency on the predator_mesh archive: "
        f"{offenders}. Promote what you need into a maintained module instead "
        "of importing a version snapshot, or widen ALLOWED_LIVE_IMPORTS with a "
        "comment saying why."
    )


def test_live_snapshot_dependency_stays_small():
    """The count is the thing an audit should read before proposing a move."""
    versions = {
        root for roots in _live_imports().values() for root in roots
        if re.fullmatch(r"predator_mesh\.v\d+", root)
    }
    # Three of 295. Everything else is reachable only from tests/ and archive/.
    assert versions == {
        "predator_mesh.v207", "predator_mesh.v208", "predator_mesh.v213",
    }, versions
