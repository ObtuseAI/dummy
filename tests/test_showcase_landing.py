from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


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


def test_standalone_system_maps_are_accessible_and_prominent() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    assets = (
        ROOT / "docs" / "assets" / "dummy-capability-map.svg",
        ROOT / "docs" / "assets" / "dummy-loop-fleet.svg",
    )

    assert landing.index('id="maps"') < landing.index('id="intelligence"')
    for asset in assets:
        root = ElementTree.parse(asset).getroot()
        assert root.attrib["role"] == "img"
        assert root.attrib["aria-labelledby"] == "title desc"
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
        assert root.find("{http://www.w3.org/2000/svg}desc") is not None
        assert f"assets/{asset.name}" in landing


def test_crypto_charts_and_loops_are_first_class_release_capabilities() -> None:
    readme = README.read_text(encoding="utf-8")
    landing = LANDING.read_text(encoding="utf-8")

    for document in (readme, landing):
        assert "DummyCryptoPaperTwin" in document
        assert "DummyCryptoHorizonEvidence" in document
        assert "Crypto Research Charts" in document
        assert "BTC" in document and "ETH" in document and "SOL" in document
        assert "15m" in document and "1h" in document and "1d" in document
    assert 'id="capabilities"' in landing
    assert 'id="crypto"' in landing
    assert "assets/dummy-crypto-charts.png" in landing
    assert (ROOT / "docs" / "assets" / "dummy-crypto-charts.png").is_file()
    assert "assets/dummy-capabilities-board.png" in landing
    assert (ROOT / "docs" / "assets" / "dummy-capabilities-board.png").is_file()
    assert "2</div><div class=\"l\">dedicated crypto loops" in landing


def test_public_release_metadata_and_policies_are_consistent() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert 'version = "1.0.0"' in project
    assert "## [1.0.0] - 2026-07-26" in changelog
    assert "Dummy Public Source License 1.0" in license_text
    assert "not an open-source distribution" in license_text
    assert "must remain strictly proprietary and private" not in license_text
    assert "public-source" in security
    assert "private repository" not in security
