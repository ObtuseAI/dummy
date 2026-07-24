from pathlib import Path
from fastapi.testclient import TestClient
from dashboard.backend.main import app

ROOT = Path(__file__).parent.parent


def test_v5_identity_endpoint():
    with TestClient(app) as client:
        r = client.get("/v5/identity")
        assert r.status_code == 200
        data = r.json()
        assert data["project"] == "Dummy"
        assert data["previous_name"] == "Dumby"


def test_v5_kalshi_status_endpoint():
    with TestClient(app) as client:
        r = client.get("/v5/kalshi/status")
        assert r.status_code == 200
        assert "credentials_present" in r.json()


def test_frontend_is_frozen_archive_source_not_a_build():
    """Wave-85: dashboard/frontend is evidence, not a buildable app.

    This used to assert a built dist/. That artifact was untracked, so the
    assertion only ever passed on a workstation that had run ``npm run build``
    -- which is why this file is workstation-only. The build tooling is gone
    (it closed all four Dependabot alerts, and the tree had an unresolvable
    vite/plugin-react peer conflict anyway), so assert what is actually true
    and load-bearing: the archived React sources survive.
    """
    frontend = ROOT / "dashboard" / "frontend"
    assert (frontend / "src" / "App.jsx").exists()
    assert (frontend / "README.md").exists()
    # No manifest may come back -- that is what reopens the alerts.
    assert not (frontend / "package.json").exists()
