"""Fix remaining Dumby references in active runtime code and tests."""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent

TARGET_DIRS = [
    "core", "adapters", "autonomy",
    "execution", "forecasting", "kalshi", "live_firewall", "repo_harvester",
    "services", "strategies", "tests",
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", "artifacts", "logs"}
SKIP_FILES = {"generate_v4_reports.py", "package-lock.json", ".env"}
TEXT_EXTS = {".py", ".toml", ".md", ".txt", ".json", ".yml", ".yaml",
             ".html", ".jsx", ".js", ".css", ".cfg", ".ini", ".example"}


def should_process(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if path.suffix.lower() not in TEXT_EXTS:
        return False
    rel = path.relative_to(ROOT)
    for part in rel.parts:
        if part in SKIP_DIRS:
            return False
    rel_posix = str(rel).replace("\\", "/")
    if "artifacts/dumby" in rel_posix:
        return False
    return any(rel_posix.startswith(d) for d in TARGET_DIRS)


def replace_safe(text: str) -> str:
    # Specific phrases first.
    text = text.replace("DUMBY_ARTIFACTS", "DUMMY_ARTIFACTS")
    text = text.replace("DUMBY_BLUNDER", "DUMMY_BLUNDER")
    text = text.replace("dumby_prob", "dummy_prob")
    text = text.replace('"dumby"', '"dummy"')
    text = text.replace("dumby.jsonl", "dummy.jsonl")
    text = text.replace("dumby.db", "dummy.db")
    text = text.replace("dumby.egg-info", "dummy.egg-info")
    text = text.replace("permitted_dumby_interface", "permitted_dummy_interface")
    # Whole-word replacements, but preserve historical V4 milestone/report tokens.
    def guard_v4(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith("DUMBY_V4") or s.startswith("dummy_v4") or s.startswith("Dummy_v4"):
            return s
        return s.replace("Dumby", "Dummy").replace("dumby", "dummy").replace("DUMBY", "DUMMY")
    # Regex matches Dumby/dumby/DUMBY whole words, including trailing underscores/numbers not allowed? Use simple.
    text = re.sub(r"\b(Dumby|dumby|DUMBY)([A-Za-z0-9_]*)?", guard_v4, text)
    return text


def main() -> None:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_process(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = replace_safe(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
            print("changed", path.relative_to(ROOT))
    print(f"done: {changed} files changed")


if __name__ == "__main__":
    main()
