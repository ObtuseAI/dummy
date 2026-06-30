import json, hashlib
from pathlib import Path

BLUNDER_ROOT = Path("C:/src/engine/obtuse/blunder")
DUMBY_BLUNDER = Path("C:/src/engine/dumby/core/inherited_blunder")

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()

def test_blunder_source_present():
    assert BLUNDER_ROOT.exists(), f"Canonical Blunder missing at {BLUNDER_ROOT}"
    assert DUMBY_BLUNDER.exists()

def test_blunder_source_unchanged():
    original = {
        p.relative_to(BLUNDER_ROOT).as_posix(): sha256_file(p)
        for p in BLUNDER_ROOT.rglob("*") if p.is_file()
        and ".git" not in p.parts and "__pycache__" not in p.parts
    }
    copied = {
        p.relative_to(DUMBY_BLUNDER).as_posix(): sha256_file(p)
        for p in DUMBY_BLUNDER.rglob("*") if p.is_file()
        and p.name != ".blunder_source_manifest.json"
        and ".git" not in p.parts and "__pycache__" not in p.parts
    }
    assert original == copied, f"Mismatched files: {set(original.keys()) ^ set(copied.keys())}"

def test_inherited_gates_exist():
    names = {p.stem.lower() for p in DUMBY_BLUNDER.rglob("*.py")}
    assert any("gate" in n for n in names), "No gate modules found in inherited Blunder"

def test_inherited_proof_ledger_exists():
    names = {p.stem.lower() for p in DUMBY_BLUNDER.rglob("*.py")}
    assert any("proof" in n or "ledger" in n for n in names), "No proof/ledger modules found"

def test_inherited_rollback_replay_exists():
    names = {p.stem.lower() for p in DUMBY_BLUNDER.rglob("*.py")}
    assert any("replay" in n or "fixture" in n for n in names), "No replay modules found"

def test_manifest_matches():
    manifest = json.loads((DUMBY_BLUNDER / ".blunder_source_manifest.json").read_text())
    for rel, h in manifest.items():
        assert (DUMBY_BLUNDER / rel).exists()
        assert sha256_file(DUMBY_BLUNDER / rel) == h
