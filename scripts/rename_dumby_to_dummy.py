"""One-off bulk string replacement for the Dummy -> Dummy canonical rename."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "artifacts", "dummy.egg-info", "dummy.egg-info", "logs",
}
SKIP_FILES = {"dummy.db", "dummy.db", ".env", "package-lock.json"}
TEXT_EXTS = {
    ".py", ".toml", ".md", ".txt", ".json", ".yml", ".yaml",
    ".html", ".jsx", ".js", ".css", ".cfg", ".ini",
}

REPLACEMENTS = [
    ("C:/src/engine/dummy", "C:/src/engine/dummy"),
    ("DummyState", "DummyState"),
    ("DummyAdapter", "DummyAdapter"),
    ("dummy_probability", "dummy_probability"),
    ("dummy-dashboard", "dummy-dashboard"),
    ("Dummy Dashboard", "Dummy Dashboard"),
    ("Dummy live trading", "Dummy live trading"),
    ("Dummy-native", "Dummy-native"),
    ("DUMMY_MODE", "DUMMY_MODE"),
    ("DUMMY_LOG_LEVEL", "DUMMY_LOG_LEVEL"),
    ("dummy.jsonl", "dummy.jsonl"),
    ("dummy.db", "dummy.db"),
    ("dummy.egg-info", "dummy.egg-info"),
    ("artifacts/dummy", "artifacts/dummy"),
]


def should_process(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    for part in rel.parts[:-1]:
        if part in SKIP_DIRS:
            return False
    if path.name in SKIP_FILES:
        return False
    if path.suffix.lower() not in TEXT_EXTS:
        return False
    rel_posix = str(rel).replace("\\", "/")
    if "artifacts/dummy" in rel_posix:
        return False
    if "proof/blunder_pre_rename_fingerprints.json" in rel_posix:
        return False
    return True


def main() -> None:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_process(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for old, new in REPLACEMENTS:
            new_text = new_text.replace(old, new)
        # General UI / doc label replacement, but not inside historical artifacts.
        if "docs/superpowers/specs/" not in str(path.relative_to(ROOT)).replace("\\", "/"):
            new_text = new_text.replace("Dummy", "Dummy")
        else:
            # Update spec titles/headings but keep historical mentions in V4 spec untouched.
            new_text = new_text.replace("Dummy → Dummy", "Dummy")
            new_text = new_text.replace("Dummy", "Dummy")
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
            print("changed", path.relative_to(ROOT))
    print(f"done: {changed} files changed")


if __name__ == "__main__":
    main()
