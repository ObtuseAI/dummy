from desktop import launch_dummy


def test_main_does_not_open_dead_board(monkeypatch):
    opened = []
    errors = []
    monkeypatch.setattr(launch_dummy, "ensure_server", lambda: False)
    monkeypatch.setattr(launch_dummy, "open_board", lambda: opened.append(True))
    monkeypatch.setattr(launch_dummy, "show_startup_error", lambda: errors.append(True))

    assert launch_dummy.main() == 1
    assert opened == []
    assert errors == [True]


def test_main_opens_ready_board(monkeypatch):
    opened = []
    monkeypatch.setattr(launch_dummy, "ensure_server", lambda: True)
    monkeypatch.setattr(launch_dummy, "open_board", lambda: opened.append(True))

    assert launch_dummy.main() == 0
    assert opened == [True]
