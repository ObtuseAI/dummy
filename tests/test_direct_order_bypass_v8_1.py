from __future__ import annotations

from pathlib import Path

from archive.report_scripts.generate_v8_1_reports import generate_direct_order_bypass_report_v8_1


def test_direct_order_bypass_report_passes_for_v8_1_files():
    report = generate_direct_order_bypass_report_v8_1()
    assert report["verdict"] == "PASS"
    assert not report["violations"]
    for checked in report["files_checked"]:
        assert Path(checked).exists() or "v8_routes.py" in checked


def test_v8_1_modules_do_not_contain_order_calls():
    root = Path("C:/src/engine/dummy")
    files = [
        root / "model_router" / "resolver.py",
        root / "model_router" / "smoke.py",
        root / "archive" / "report_scripts" / "generate_v8_1_reports.py",
        root / "archive" / "routes" / "v8_routes.py",
    ]
    disallowed = [
        "create_order(",
        "cancel_order(",
        "/orders",
        "portfolio/orders",
    ]
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in disallowed:
            assert token.lower() not in text, f"{path} contains {token}"
