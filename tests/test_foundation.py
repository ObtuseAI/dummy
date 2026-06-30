import os
from core.ontology import AccountMode, CapConfig, Forecast, LiveOrderRequest
from core.config_loader import load_caps
from core.secret_guard import redact
from core.state import DumbyState

def test_load_caps_defaults():
    caps = load_caps()
    assert caps.max_single_order_cents == 100
    assert caps.allow_market_orders is False
    assert caps.limit_orders_only is True

def test_secret_redaction():
    os.environ["KALSHI_API_KEY_ID"] = "supersecret1234"
    from core import secret_guard
    if "supersecret1234" not in secret_guard._SECRET_VALUES:
        secret_guard._SECRET_VALUES.append("supersecret1234")
    out = redact({"msg": "key=supersecret1234"})
    assert "supersecret1234" not in str(out)
    assert "***REDACTED***" in str(out)

def test_state_mode_transitions():
    s = DumbyState()
    s.set_mode(AccountMode.READ_ONLY)
    assert s.mode == AccountMode.READ_ONLY
    s.enable_kill_switch("test")
    assert s.kill_switch.active
    s.trigger_emergency_stop()
    assert s.emergency_stop.active
