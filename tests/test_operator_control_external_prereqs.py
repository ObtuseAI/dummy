"""Focused tests for the Operator Control external-prerequisites workflow.

These tests verify fail-closed validation, typed-confirmation gating, safe file
writes with backups/hashes, and the absence of broker contact / raw secrets.
All file paths are redirected to a temporary directory so the real repo configs
are never mutated.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest import mock

import pytest

MOD_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "backend" / "operator_control_routes.py"
_spec = importlib.util.spec_from_file_location("operator_control_routes", MOD_PATH)
ocr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ocr)


class FakeProc:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Redirect all operator-controlled paths into a temp directory."""
    root = tmp_path / "dummy_root"
    root.mkdir()
    monkeypatch.setattr(ocr, "DUMMY_ROOT", root)
    monkeypatch.setattr(ocr, "OPERATOR_EXTERNAL_DIR", root / "runtime" / "operator_external")
    monkeypatch.setattr(
        ocr,
        "ADAPTER_DESCRIPTOR_PATH",
        root / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json",
    )
    monkeypatch.setattr(ocr, "LIVE_SUBMIT_PATH", root / "configs" / "live_submit.json")
    monkeypatch.setattr(ocr, "CAPS_PATH", root / "configs" / "caps.json")
    monkeypatch.setattr(
        ocr,
        "APPROVAL_PATH",
        root / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json",
    )
    # Stage the real adapter module so registration/check-all can verify it.
    write_real_adapter_module(root)
    return root


@pytest.fixture
def no_subprocess():
    """Mock subprocess.run so no real CLI is ever invoked."""
    with mock.patch.object(ocr.subprocess, "run", return_value=FakeProc(0, "ready")) as m:
        yield m


def valid_descriptor():
    return {
        "broker": "KALSHI",
        "adapter_name": "RealKalshiLimitAdapter",
        "adapter_module_path": "predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py",
        "limit_order_endpoint_label": "kalshi-limit-order",
        "credential_reference_names": ["KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM"],
        "endpoint_env_ref": "KALSHI_API_BASE",
        "adapter_type": "LiveBrokerFirewall",
        "order_type_policy": "LIMIT_ONLY",
        "market_orders_allowed": False,
        "credential_source": "env_ref",
    }


def write_real_adapter_module(root, rel_path="predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py"):
    """Create a minimal importable real adapter module under the temp repo root."""
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "class KalshiLiveBrokerFirewallAdapter:\n"
        "    @staticmethod\n"
        "    def validate_environment():\n"
        "        return True\n"
    )


def _future_expiry() -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_live_submit_body():
    return {
        "enabled": True,
        "operator": "chris",
        "reason": "one controlled proof",
        "expiry": _future_expiry(),
        "proof_scope": "one_controlled_proof",
        "typed_confirmation": ocr.LIVE_SUBMIT_TYPED_CONFIRMATION,
    }


def valid_caps_body():
    return {
        "max_order_count": 1,
        "max_order_size": 100,
        "order_type_policy": "LIMIT_ONLY",
        "market_orders_allowed": False,
        "kill_switch_enabled": True,
        "max_daily_loss": 500,
        "max_open_exposure": 1000,
        "operator": "chris",
        "reason": "strict one-proof caps",
        "expiry": _future_expiry(),
        "typed_confirmation": ocr.CAPS_TYPED_CONFIRMATION,
    }


# ---------------------------------------------------------------------------
# Adapter descriptor validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_validate_accepts_env_ref_reference():
    body = ocr.AdapterDescriptorBody(descriptor=valid_descriptor())
    res = await ocr.adapter_validate(body)
    assert res["ok"] is True
    assert res["errors"] == []


@pytest.mark.parametrize("marker", ["stub", "test", "dummy", "fixture"])
@pytest.mark.asyncio
async def test_adapter_validate_rejects_stub_test_dummy_fixture_markers(marker):
    desc = valid_descriptor()
    desc["adapter_name"] = f"My {marker} adapter"
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("banned" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_adapter_validate_rejects_raw_secret_field():
    desc = valid_descriptor()
    desc["api_key_secret"] = "x" * 80  # long, space-less value
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("raw secret" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_adapter_validate_rejects_bad_credential_reference():
    desc = valid_descriptor()
    desc["credential_reference_names"] = ["sk-1234567890abcdef"]
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("reference" in e.lower() for e in res["errors"])


@pytest.mark.parametrize("marker", ["stub", "test", "dummy", "fixture"])
@pytest.mark.asyncio
async def test_adapter_validate_rejects_stub_module_path(marker):
    desc = valid_descriptor()
    desc["adapter_module_path"] = f"predator_mesh/brokers/{marker}_kalshi.py"
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("banned" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_adapter_validate_rejects_disallowed_module_path():
    desc = valid_descriptor()
    desc["adapter_module_path"] = "adapters/untrusted_adapter.py"
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("allowed real-adapter module list" in e for e in res["errors"])


@pytest.mark.asyncio
async def test_adapter_validate_rejects_missing_kalshi_private_key_ref():
    desc = valid_descriptor()
    desc["credential_reference_names"] = ["KALSHI_API_KEY_ID"]
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is False
    assert any("private-key credential reference" in e for e in res["errors"])


@pytest.mark.asyncio
async def test_adapter_validate_accepts_legacy_private_key_ref():
    desc = valid_descriptor()
    desc["credential_reference_names"] = ["KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"]
    body = ocr.AdapterDescriptorBody(descriptor=desc)
    res = await ocr.adapter_validate(body)
    assert res["ok"] is True
    assert res["errors"] == []


# ---------------------------------------------------------------------------
# Adapter registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_register_blocks_without_typed_confirmation(paths):
    desc = valid_descriptor()
    body = ocr.AdapterRegisterBody(descriptor=desc, typed_confirmation="not the right sentence")
    res = await ocr.adapter_register(body)
    assert res["ok"] is False
    assert not ocr.ADAPTER_DESCRIPTOR_PATH.exists()


@pytest.mark.asyncio
async def test_adapter_register_blocks_if_checkboxes_missing(paths):
    desc = valid_descriptor()
    body = ocr.AdapterRegisterBody(
        descriptor=desc,
        operator_confirm_adapter_real=True,
        operator_confirm_not_stub=False,
        operator_confirm_limit_only=True,
        typed_confirmation=ocr.ADAPTER_TYPED_CONFIRMATION,
    )
    res = await ocr.adapter_register(body)
    assert res["ok"] is False
    assert not ocr.ADAPTER_DESCRIPTOR_PATH.exists()


@pytest.mark.asyncio
async def test_adapter_register_writes_descriptor_under_safe_path(paths):
    desc = valid_descriptor()
    body = ocr.AdapterRegisterBody(
        descriptor=desc,
        operator_confirm_adapter_real=True,
        operator_confirm_not_stub=True,
        operator_confirm_limit_only=True,
        typed_confirmation=ocr.ADAPTER_TYPED_CONFIRMATION,
    )
    res = await ocr.adapter_register(body)
    assert res["ok"] is True
    assert ocr.ADAPTER_DESCRIPTOR_PATH.exists()
    written = json.loads(ocr.ADAPTER_DESCRIPTOR_PATH.read_text())
    assert written["adapter_type"] == "LiveBrokerFirewall"
    assert written["broker"] == "KALSHI"
    assert written["credential_reference_names"] == ["KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM"]
    assert "api_key" not in written
    assert res["hash_after"] is not None


@pytest.mark.asyncio
async def test_adapter_smoke_is_no_contact_descriptor_validation():
    body = ocr.AdapterDescriptorBody(descriptor=valid_descriptor())
    res = await ocr.adapter_smoke(body)
    assert res["ok"] is True
    assert any("no broker contact" in n.lower() for n in res["safety_notes"])


# ---------------------------------------------------------------------------
# Live-submit workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_submit_preview_does_not_write(paths):
    body = ocr.LiveSubmitBody(**valid_live_submit_body())
    res = await ocr.live_submit_preview(body)
    assert res["ok"] is True
    assert res["will_write"] is False
    assert not ocr.LIVE_SUBMIT_PATH.exists()


@pytest.mark.asyncio
async def test_live_submit_write_requires_typed_confirmation(paths):
    body = ocr.LiveSubmitBody(**{**valid_live_submit_body(), "typed_confirmation": "wrong"})
    res = await ocr.live_submit_write(body)
    assert res["ok"] is False
    assert not ocr.LIVE_SUBMIT_PATH.exists()


@pytest.mark.asyncio
async def test_live_submit_write_creates_backup_and_hash_changes(paths):
    ocr.LIVE_SUBMIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    initial = {"enabled": False, "operator": "none", "timestamp": "old", "reason": "old"}
    ocr.LIVE_SUBMIT_PATH.write_text(json.dumps(initial))
    hash_before = ocr._sha256_file(ocr.LIVE_SUBMIT_PATH)

    res = await ocr.live_submit_write(ocr.LiveSubmitBody(**valid_live_submit_body()))
    assert res["ok"] is True
    assert res["hash_before"] == hash_before
    assert res["hash_after"] != hash_before
    assert res["backup_path"] is not None
    assert Path(res["backup_path"]).exists()

    written = json.loads(ocr.LIVE_SUBMIT_PATH.read_text())
    assert written["enabled"] is True
    assert written["explicit_acknowledgement"] == ocr.LIVE_SUBMIT_REQUIRED_ACK


@pytest.mark.asyncio
async def test_live_submit_disable_relocks(paths):
    # First enable.
    await ocr.live_submit_write(ocr.LiveSubmitBody(**valid_live_submit_body()))
    assert json.loads(ocr.LIVE_SUBMIT_PATH.read_text())["enabled"] is True

    res = await ocr.live_submit_disable()
    assert res["ok"] is True
    written = json.loads(ocr.LIVE_SUBMIT_PATH.read_text())
    assert written["enabled"] is False
    assert "explicit_acknowledgement" not in written


# ---------------------------------------------------------------------------
# Caps workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caps_preview_does_not_write(paths):
    body = ocr.CapsBody(**valid_caps_body())
    res = await ocr.caps_preview(body)
    assert res["ok"] is True
    assert res["will_write"] is False
    assert not ocr.CAPS_PATH.exists()


@pytest.mark.asyncio
async def test_caps_write_rejects_market_orders(paths):
    body = ocr.CapsBody(**{**valid_caps_body(), "market_orders_allowed": True})
    res = await ocr.caps_write(body)
    assert res["ok"] is False
    assert any("market" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_caps_write_rejects_kill_switch_false(paths):
    body = ocr.CapsBody(**{**valid_caps_body(), "kill_switch_enabled": False})
    res = await ocr.caps_write(body)
    assert res["ok"] is False
    assert any("kill" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_caps_write_rejects_max_order_count_above_one(paths):
    body = ocr.CapsBody(**{**valid_caps_body(), "max_order_count": 2})
    res = await ocr.caps_write(body)
    assert res["ok"] is False
    assert any("max_order_count" in e.lower() for e in res["errors"])


@pytest.mark.asyncio
async def test_caps_write_requires_typed_confirmation(paths):
    body = ocr.CapsBody(**{**valid_caps_body(), "typed_confirmation": "nope"})
    res = await ocr.caps_write(body)
    assert res["ok"] is False
    assert not ocr.CAPS_PATH.exists()


@pytest.mark.asyncio
async def test_caps_write_creates_backup_and_hash_changes(paths):
    ocr.CAPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    initial = {"max_single_order_cents": 100, "limit_orders_only": True, "kill_switch_required": True}
    ocr.CAPS_PATH.write_text(json.dumps(initial))
    hash_before = ocr._sha256_file(ocr.CAPS_PATH)

    res = await ocr.caps_write(ocr.CapsBody(**valid_caps_body()))
    assert res["ok"] is True
    assert res["hash_before"] == hash_before
    assert res["hash_after"] != hash_before
    assert res["backup_path"] is not None
    assert Path(res["backup_path"]).exists()

    written = json.loads(ocr.CAPS_PATH.read_text())
    assert written["order_type_policy"] == "LIMIT_ONLY"
    assert written["market_orders_allowed"] is False
    assert written["kill_switch_enabled"] is True
    assert written["max_order_count"] == 1


@pytest.mark.asyncio
async def test_caps_relock_resets_safe_state(paths):
    await ocr.caps_write(ocr.CapsBody(**valid_caps_body()))
    res = await ocr.caps_relock()
    assert res["ok"] is True
    written = json.loads(ocr.CAPS_PATH.read_text())
    assert written["max_order_count"] == 0
    assert written["max_order_size"] == 0
    assert written["market_orders_allowed"] is False
    assert written["kill_switch_enabled"] is True


# ---------------------------------------------------------------------------
# Check-all / status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_all_reports_blockers_when_missing(paths, no_subprocess):
    res = await ocr.external_prereqs_check_all()
    assert res["ok"] is False
    assert res["ready"] is False
    assert len(res["blockers"]) >= 3
    blocker_text = " ".join(res["blockers"]).lower()
    assert "adapter" in blocker_text
    assert "live-submit" in blocker_text or "caps" in blocker_text


@pytest.mark.asyncio
async def test_check_all_reports_ready_when_all_valid(paths, no_subprocess, monkeypatch):
    # Satisfy the credential env refs without reading their values.
    for ref in ("KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM", "KALSHI_API_BASE"):
        monkeypatch.setenv(ref, "present")

    # Adapter.
    await ocr.adapter_register(
        ocr.AdapterRegisterBody(
            descriptor=valid_descriptor(),
            operator_confirm_adapter_real=True,
            operator_confirm_not_stub=True,
            operator_confirm_limit_only=True,
            typed_confirmation=ocr.ADAPTER_TYPED_CONFIRMATION,
        )
    )
    # Live-submit.
    await ocr.live_submit_write(ocr.LiveSubmitBody(**valid_live_submit_body()))
    # Caps.
    await ocr.caps_write(ocr.CapsBody(**valid_caps_body()))
    # Approval.
    ocr.APPROVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    ocr.APPROVAL_PATH.write_text(json.dumps({"scope": "one_controlled_production_pilot"}))

    res = await ocr.external_prereqs_check_all()
    assert res["ready"] is True
    assert res["blockers"] == []
    assert res["adapter"]["contract"]["contract_satisfied"] is True
    assert res["adapter"]["credentials_missing"] == []


@pytest.mark.asyncio
async def test_check_all_blocks_when_adapter_env_refs_missing(paths, no_subprocess):
    # Stage a valid adapter descriptor and module, but do NOT set env refs.
    await ocr.adapter_register(
        ocr.AdapterRegisterBody(
            descriptor=valid_descriptor(),
            operator_confirm_adapter_real=True,
            operator_confirm_not_stub=True,
            operator_confirm_limit_only=True,
            typed_confirmation=ocr.ADAPTER_TYPED_CONFIRMATION,
        )
    )
    res = await ocr.external_prereqs_check_all()
    assert res["ready"] is False
    assert any("credential environment references missing" in b for b in res["blockers"])


@pytest.mark.asyncio
async def test_status_includes_external_prereq_summary(paths, no_subprocess):
    res = await ocr.external_prereqs_status()
    assert "adapter" in res
    assert "live_submit" in res
    assert "caps" in res
    assert "blockers" in res


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_shot_live_still_requires_exact_env_confirmation():
    body = ocr.OneShotLiveBody(
        live_proof_mode="1",
        live_proof_ack=ocr.ENV_ACK_VAL,
        typed_confirm="not the exact sentence",
    )
    with mock.patch.object(ocr.subprocess, "run") as run:
        res = await ocr.one_shot_live(body)
    assert res["refused"] is True
    run.assert_not_called()


def test_new_endpoints_do_not_call_execute_once(paths):
    """Adapter endpoints and preview endpoints must never invoke subprocess."""
    async def exercise():
        desc = valid_descriptor()
        await ocr.adapter_validate(ocr.AdapterDescriptorBody(descriptor=desc))
        await ocr.adapter_smoke(ocr.AdapterDescriptorBody(descriptor=desc))
        await ocr.live_submit_preview(ocr.LiveSubmitBody(**valid_live_submit_body()))
        await ocr.caps_preview(ocr.CapsBody(**valid_caps_body()))

    with mock.patch.object(ocr.subprocess, "run") as run:
        import asyncio
        asyncio.run(exercise())
    run.assert_not_called()


def test_no_endpoint_stores_raw_secrets(paths):
    desc = valid_descriptor()
    desc["credential_reference_names"] = ["x" * 80]
    body = ocr.AdapterRegisterBody(
        descriptor=desc,
        operator_confirm_adapter_real=True,
        operator_confirm_not_stub=True,
        operator_confirm_limit_only=True,
        typed_confirmation=ocr.ADAPTER_TYPED_CONFIRMATION,
    )
    import asyncio
    res = asyncio.run(ocr.adapter_register(body))
    assert res["ok"] is False
    assert not ocr.ADAPTER_DESCRIPTOR_PATH.exists()


def test_path_traversal_blocked():
    root = Path("/tmp/safe_root")
    with pytest.raises(ValueError):
        ocr._safe_relative_path("../etc/passwd", root)
    with pytest.raises(ValueError):
        ocr._safe_relative_path("foo/../../../etc/passwd", root)


# ---------------------------------------------------------------------------
# No broker contact assertion (by construction / mocking)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_all_uses_one_shot_check_not_broker_adapter(paths, no_subprocess):
    await ocr.external_prereqs_check_all()
    cmds = [" ".join(c.args[0]) for c in no_subprocess.call_args_list]
    joined = " ".join(cmds).lower()
    assert "one-shot-check" in joined
    assert "execute-once" not in joined
    assert "broker" not in joined


@pytest.mark.asyncio
async def test_one_shot_live_armed_runs_full_completion_not_execute_once():
    body = ocr.OneShotLiveBody(
        live_proof_mode="1",
        live_proof_ack=ocr.ENV_ACK_VAL,
        typed_confirm=ocr.TYPED_CONFIRM_SENTENCE,
    )
    with mock.patch.object(ocr.subprocess, "run", return_value=FakeProc(0, "live proof ok")) as run:
        res = await ocr.one_shot_live(body)
    assert not res.get("refused")
    cmd = run.call_args[0][0]
    assert "operator_full_completion.py" in cmd[1]
    assert "one-shot-live" in cmd
    joined = " ".join(cmd)
    assert "execute-once" not in joined
    assert "broker" not in joined
    assert "--market" not in joined
    assert "--scale" not in joined
    assert "--autonomy" not in joined

