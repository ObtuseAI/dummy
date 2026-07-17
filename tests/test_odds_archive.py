"""Wave-12: the Odds API payload archive (paid fetches persisted, fail-open)."""
from __future__ import annotations

import gzip
import json

from autonomy.odds_api_budget import OddsApiBudget


class _Clock:
    def __init__(self, t=1_784_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _budget(tmp_path, clock=None, **kwargs):
    return OddsApiBudget(
        daily_credits=500,
        budget_path=tmp_path / "budget.json",
        cache_dir=tmp_path / "cache",
        archive_dir=kwargs.pop("archive_dir", tmp_path / "archive"),
        now_fn=clock or _Clock(),
        **kwargs,
    )


def _read_archive(budget):
    shards = sorted(budget.archive_dir.glob("odds_*.jsonl.gz"))
    lines = []
    for shard in shards:
        with gzip.open(shard, "rt", encoding="utf-8") as fh:
            lines.extend(json.loads(line) for line in fh if line.strip())
    return lines


def test_live_paid_fetch_is_archived(tmp_path):
    budget = _budget(tmp_path)

    def fetch():
        return [{"home_team": "New York Yankees"}], 19_997

    payload, src = budget.budgeted_fetch("odds|baseball_mlb|h2h,totals,spreads|us", fetch)
    assert src == "live"
    rows = _read_archive(budget)
    assert len(rows) == 1
    assert rows[0]["key"] == "odds|baseball_mlb|h2h,totals,spreads|us"
    assert rows[0]["remaining"] == 19_997
    assert rows[0]["payload"] == [{"home_team": "New York Yankees"}]
    assert rows[0]["ts"] == budget._now()


def test_cache_hits_and_free_fetches_are_not_archived(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)

    def fetch():
        return [{"v": 1}], None

    budget.budgeted_fetch("k", fetch)
    budget.budgeted_fetch("k", fetch)                 # cache hit: no new row
    budget.budgeted_fetch("sports_list", fetch, cost=0)   # free: never archived
    rows = _read_archive(budget)
    assert len(rows) == 1


def test_appended_members_stay_one_readable_stream(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)
    budget.budgeted_fetch("a", lambda: ([1], None))
    clock.t += 5000                                    # past TTL, same month
    budget.budgeted_fetch("a", lambda: ([2], None))
    budget.budgeted_fetch("b", lambda: ([3], None))
    rows = _read_archive(budget)
    assert [r["payload"] for r in rows] == [[1], [2], [3]]
    assert len(list(budget.archive_dir.glob("odds_*.jsonl.gz"))) == 1


def test_shards_split_by_month(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)
    budget.budgeted_fetch("a", lambda: ([1], None))
    clock.t += 32 * 24 * 3600                          # next month
    budget.budgeted_fetch("b", lambda: ([2], None))
    assert len(list(budget.archive_dir.glob("odds_*.jsonl.gz"))) == 2


def test_archive_failure_never_breaks_the_fetch(tmp_path):
    # Point the archive at a path whose parent is a FILE: mkdir fails.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    budget = _budget(tmp_path, archive_dir=blocker / "archive")
    payload, src = budget.budgeted_fetch("k", lambda: ([{"ok": 1}], 5))
    assert src == "live" and payload == [{"ok": 1}]    # fetch path undisturbed
    assert budget.status()["spent_today"] > 0


def test_env_override_sets_archive_dir(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("DUMMY_ODDS_ARCHIVE_DIR", str(target))
    budget = OddsApiBudget(
        budget_path=tmp_path / "budget.json",
        cache_dir=tmp_path / "cache",
        now_fn=_Clock(),
    )
    assert budget.archive_dir == target
    budget.budgeted_fetch("k", lambda: ([1], None))
    assert list(target.glob("odds_*.jsonl.gz"))
