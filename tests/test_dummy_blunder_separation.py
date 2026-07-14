from pathlib import Path
import json

ROOT = Path(__file__).parent.parent
BLUNDER_ROOT = Path("C:/src/engine/obtuse/blunder")


def test_blunder_root_exists():
    assert BLUNDER_ROOT.exists(), "canonical Blunder root missing"


def test_dummy_does_not_import_canonical_blunder():
    offenders = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT)
        if any(p in {"archive", ".git", "__pycache__", ".pytest_cache", "tests", "scripts"} for p in rel.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if "obtuse.blunder" in text or str(BLUNDER_ROOT) in text:
            offenders.append(str(rel))
    assert not offenders, f"non-test code references canonical Blunder: {offenders}"


def test_dummy_has_own_configs_logs_artifacts():
    assert (ROOT / "configs").exists()
    assert (ROOT / "logs").exists()
    assert (ROOT / "artifacts").exists()
    assert (ROOT / "proof").exists()


def test_pre_rename_blunder_fingerprints_unchanged():
    pre_path = ROOT / "proof" / "blunder_pre_rename_fingerprints.json"
    assert pre_path.exists(), "pre-rename Blunder fingerprints missing"
    pre = json.loads(pre_path.read_text())
    import hashlib
    post = {}
    for p in sorted(BLUNDER_ROOT.rglob("*")):
        if p.is_file():
            post[str(p.relative_to(BLUNDER_ROOT)).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest()
    assert pre["fingerprints"] == post, "canonical Blunder files changed during rename"
