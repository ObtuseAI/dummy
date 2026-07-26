"""Filesystem-lazy paths for gitignored evidence/report trees.

Every ``archive/report_scripts/generate_v*_reports.py`` (and ``services/
reports.py``, and ``core/logger.py``) used to materialise its output directory
as an *import side effect*::

    ARTIFACTS = ROOT / "artifacts" / "dummy"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)   # <- ran at import

pytest imports every test module -- and therefore every module those tests
import -- during **collection**, long before any fixture can redirect anything.
So merely collecting the suite created the gitignored ``artifacts/dummy`` tree.
That made the suite order-dependent: ``tests/conftest.py`` probes for that
directory to decide whether workstation-only governance evidence is available,
so a fresh clone passed on run 1 (everything skipped) and reported 281 failures
on run 2 (everything un-skipped against an empty directory).

``EvidencePath`` keeps the ordinary ``BASE / "name"`` ergonomics of ``Path``
but moves directory creation to the moment a file is actually *written*.
Reading, existence probing and iteration never create anything, so importing a
report module is now inert. Production behaviour is unchanged: the first real
report write still creates the tree exactly as before.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any


class EvidencePath(type(Path())):
    """A ``Path`` whose parent directory is created at write time.

    The runtime-specific concrete path class is required for Python 3.11,
    where directly subclassing ``pathlib.Path`` leaves ``_flavour`` undefined.
    This remains a ``Path`` subclass and makes ``/``, ``.parent``, ``.glob()``
    and friends return ``EvidencePath`` as well, so a single wrapper at the
    base-directory constant propagates to every derived report path.
    """

    __slots__ = ()

    def _ensure_dir(self) -> None:
        parent = self.parent
        if not parent.is_dir():
            parent.mkdir(parents=True, exist_ok=True)

    def open(  # type: ignore[override]
        self, mode: str = "r", *args: Any, **kwargs: Any
    ) -> IO[Any]:
        if any(flag in mode for flag in "wxa+"):
            self._ensure_dir()
        return super().open(mode, *args, **kwargs)

    def write_text(self, *args: Any, **kwargs: Any) -> int:
        self._ensure_dir()
        return super().write_text(*args, **kwargs)

    def write_bytes(self, *args: Any, **kwargs: Any) -> int:
        self._ensure_dir()
        return super().write_bytes(*args, **kwargs)

    def touch(self, *args: Any, **kwargs: Any) -> None:
        self._ensure_dir()
        return super().touch(*args, **kwargs)
