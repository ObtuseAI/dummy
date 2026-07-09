from pathlib import Path
import json

from core.live_submit_state import (
    LIVE_SUBMIT_REQUIRED_ACK,
    LiveSubmitState,
    classify_live_submit_state,
    validate_default_disabled,
)

ROOT = Path(__file__).parent.parent


def test_live_submit_defaults_to_disabled():
    path = ROOT / "configs" / "live_submit.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data.get("enabled") is False


def test_default_state_validates_as_disabled():
    path = ROOT / "configs" / "live_submit.json"
    data = json.loads(path.read_text())
    result = validate_default_disabled(data)
    assert result.ok is True
    assert classify_live_submit_state(data) is LiveSubmitState.DEFAULT_DISABLED_VALID


def test_live_submit_requires_explicit_acknowledgement():
    from live_firewall.firewall import LiveBrokerFirewall
    from live_firewall.exposure_tracker import ExposureTracker
    fw = LiveBrokerFirewall(None, ExposureTracker())
    # A default fresh config should not enable live submit.
    assert fw._live_submit_enabled() is False


def test_firewall_required_acknowledgement_matches_state_model():
    from live_firewall.firewall import LiveBrokerFirewall
    assert LiveBrokerFirewall.REQUIRED_ACKNOWLEDGEMENT == LIVE_SUBMIT_REQUIRED_ACK
