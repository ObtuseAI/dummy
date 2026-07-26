from pathlib import Path

from core.evidence_dir import EvidencePath


def test_evidence_path_is_concrete_and_read_checks_are_inert(tmp_path: Path) -> None:
    path = EvidencePath(tmp_path / "nested" / "evidence.json")

    assert isinstance(path, Path)
    assert isinstance(path.parent, EvidencePath)
    assert isinstance(path.with_name("other.json"), EvidencePath)
    assert not path.exists()
    assert not path.parent.exists()


def test_evidence_path_creates_parent_only_when_written(tmp_path: Path) -> None:
    path = EvidencePath(tmp_path / "nested" / "evidence.json")

    path.write_text("first", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("-second")

    assert path.read_text(encoding="utf-8") == "first-second"
