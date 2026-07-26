from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "docs" / "index.html"
README = ROOT / "README.md"


class _LandingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.images: list[str] = []
        self.scripts = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "a" and values.get("href"):
            self.hrefs.append(str(values["href"]))
        if tag == "img" and values.get("src"):
            self.images.append(str(values["src"]))
        if tag == "script":
            self.scripts += 1


def _landing() -> tuple[str, _LandingParser]:
    html = LANDING.read_text(encoding="utf-8")
    parser = _LandingParser()
    parser.feed(html)
    return html, parser


def test_landing_internal_links_and_images_are_complete() -> None:
    _, parser = _landing()

    missing_targets = {
        href for href in parser.hrefs if href.startswith("#") and href[1:] not in parser.ids
    }
    assert not missing_targets
    assert parser.images
    assert all(not src.startswith(("http://", "https://")) for src in parser.images)
    assert all((LANDING.parent / src).is_file() for src in parser.images)


def test_landing_showcases_the_intelligence_loop_without_overclaiming() -> None:
    html, parser = _landing()

    for capability in (
        "Perception",
        "Probabilistic reasoning",
        "Dissent",
        "Memory",
        "Metacognition",
        "Constrained action",
    ):
        assert capability in html
    for phase in (
        "Scan",
        "Signal",
        "Fuse",
        "Allocate",
        "Risk",
        "Execute",
        "Reconcile",
        "Learn",
    ):
        assert f"<h3>{phase}</h3>" in html
    assert "45 loops, isolated by responsibility" in html
    assert "0</div><div class=\"l\">automatic authority" in html
    assert "Current launch status remains" in html
    assert "<strong>NO-GO</strong>" in html
    assert "LIVE · SHADOW" not in html
    assert parser.scripts == 0


def test_readme_and_landing_share_the_same_proof_boundary() -> None:
    readme = README.read_text(encoding="utf-8")
    landing = LANDING.read_text(encoding="utf-8")

    assert "## The intelligence loop" in readme
    assert "Observe" in readme
    assert "Gate" in readme
    assert "5,068 collected" in readme
    assert "The evidence ladder" in landing
    assert "Forecast" in landing
    assert "Settled evidence" in landing
    assert "Promotion" in landing
    assert "Authority" in landing


def test_landing_contains_accessible_diagrams_and_current_ui_gallery() -> None:
    landing = LANDING.read_text(encoding="utf-8")

    assert 'id="capability-diagram"' in landing
    assert 'aria-labelledby="cap-title cap-desc"' in landing
    assert "<title id=\"cap-title\">Dummy intelligence capability diagram</title>" in landing
    assert 'id="loop-fleet-diagram"' in landing
    assert 'aria-labelledby="fleet-title fleet-desc"' in landing
    assert "<title id=\"fleet-title\">Dummy 45-loop fleet diagram</title>" in landing
    assert landing.count("<svg ") == 2
    assert landing.count("assets/dummy-overview.png") == 2
    assert "assets/dummy-sports-scope.png" in landing
    assert "assets/dummy-crypto-scope.png" in landing
    assert "Updated UI capture" in landing
