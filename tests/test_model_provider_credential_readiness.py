from __future__ import annotations


from model_router.credential_readiness import CredentialReadiness, ModelCredentialStatus


class TestCredentialReadiness:
    def test_deepseek_defaults_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

        readiness = CredentialReadiness()
        status = readiness.deepseek_status()
        assert status.present is False
        assert status.base_url == "https://api.deepseek.com"
        assert status.model == "deepseekv4flash"
        assert status.source == "env"
        assert status.redacted is True

    def test_minimax_defaults_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
        monkeypatch.delenv("MINIMAX_MODEL", raising=False)

        readiness = CredentialReadiness()
        status = readiness.minimax_status()
        assert status.present is False
        assert status.base_url == "https://api.minimax.chat"
        assert status.model == "minimaxm3"
        assert status.source == "env"
        assert status.redacted is True

    def test_deepseek_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.deepseek.example")
        monkeypatch.setenv("DEEPSEEK_MODEL", "custom-deepseek-model")

        readiness = CredentialReadiness()
        status = readiness.deepseek_status()
        assert status.present is True
        assert status.base_url == "https://custom.deepseek.example"
        assert status.model == "custom-deepseek-model"

    def test_minimax_env_overrides(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")
        monkeypatch.setenv("MINIMAX_BASE_URL", "https://custom.minimax.example")
        monkeypatch.setenv("MINIMAX_MODEL", "custom-minimax-model")

        readiness = CredentialReadiness()
        status = readiness.minimax_status()
        assert status.present is True
        assert status.base_url == "https://custom.minimax.example"
        assert status.model == "custom-minimax-model"

    def test_status_never_contains_api_key(self, monkeypatch):
        secret = "sk-deepseek-never-leak-1234567890abcdef"
        monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
        status = CredentialReadiness().deepseek_status()
        status_dict = status.as_dict()
        assert "api_key" not in status_dict
        assert secret not in str(status_dict)
        assert status_dict["redacted"] is True

    def test_all_statuses_and_ready(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        readiness = CredentialReadiness()
        assert set(readiness.all_statuses().keys()) == {
            "deepseek", "minimax", "openrouter"}
        assert readiness.ready() is False

        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-mm")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
        assert readiness.ready() is True


class TestOpenRouterReadiness:
    """The panel authenticates with OPENROUTER_API_KEY, so readiness must
    cover it -- otherwise a missing panel credential only ever surfaces
    downstream as a router fallback."""

    def test_openrouter_defaults_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        status = CredentialReadiness().openrouter_status()

        assert status.present is False
        assert status.base_url == "https://openrouter.ai/api"
        assert status.model == "openrouter/auto"
        assert status.source == "env"
        assert status.redacted is True

    def test_openrouter_env_overrides(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://custom.openrouter.example")
        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/custom-model")

        status = CredentialReadiness().openrouter_status()

        assert status.present is True
        assert status.base_url == "https://custom.openrouter.example"
        assert status.model == "vendor/custom-model"

    def test_blank_key_is_not_present(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "   ")

        assert CredentialReadiness().openrouter_status().present is False

    def test_missing_openrouter_key_makes_the_surface_not_ready(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-mm")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        assert CredentialReadiness().ready() is False

    def test_openrouter_status_never_contains_the_key(self, monkeypatch):
        secret = "sk-or-v1-never-leak-1234567890abcdef"
        monkeypatch.setenv("OPENROUTER_API_KEY", secret)

        status_dict = CredentialReadiness().openrouter_status().as_dict()

        assert "api_key" not in status_dict
        assert secret not in str(status_dict)
        assert status_dict["redacted"] is True


class TestModelCredentialStatus:
    def test_as_dict_is_redacted(self):
        status = ModelCredentialStatus(
            present=True,
            base_url="https://api.example.com",
            model="example",
            source="env",
        )
        d = status.as_dict()
        assert d == {
            "present": True,
            "base_url": "https://api.example.com",
            "model": "example",
            "source": "env",
            "redacted": True,
        }
