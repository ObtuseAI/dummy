import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.ontology import AccountMode, KillSwitchState, EmergencyStopState


DEFAULT_RISK_STATE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "risk_state.json"
RISK_STATE_SCHEMA_VERSION = 2


class DummyState:
    """Process state plus the persisted UTC daily realized-loss counter.

    Ad-hoc/test instances are in-memory by default. The module singleton below
    opts into persistence so the live firewall cannot forget losses on restart.
    """

    def __init__(self, *, persist: bool = False, state_path: Path | None = None):
        self.mode = AccountMode.OFF
        self.kill_switch = KillSwitchState(active=False)
        self.emergency_stop = EmergencyStopState(active=False)
        self.kalshi_connected = False
        self.balance_cents = 0
        configured_path = os.environ.get("DUMMY_RISK_STATE_PATH")
        self._state_path = state_path or (Path(configured_path) if configured_path else DEFAULT_RISK_STATE_PATH)
        self._persist_enabled = persist
        self._daily_loss_cents = 0
        self._daily_loss_date = datetime.now(timezone.utc).date().isoformat()
        self._processed_settlements: set[str] = set()
        self.daily_loss_window_start = datetime.now(timezone.utc)
        self.persistence_error: str | None = None
        if self._persist_enabled:
            self._load_risk_state()

    @property
    def daily_loss_cents(self) -> int:
        self._rollover_if_needed()
        return self._daily_loss_cents

    @daily_loss_cents.setter
    def daily_loss_cents(self, value: int) -> None:
        self._daily_loss_cents = max(0, int(value))

    def _rollover_if_needed(self) -> None:
        if self.persistence_error is not None:
            return
        today = datetime.now(timezone.utc).date().isoformat()
        if self._daily_loss_date == today:
            return
        self._daily_loss_date = today
        self._daily_loss_cents = 0
        self._processed_settlements.clear()
        self.daily_loss_window_start = datetime.now(timezone.utc)
        self._persist_risk_state()

    def _activate_safety_controls_fail_closed(self, reason: str) -> None:
        now = datetime.now(timezone.utc)
        self.kill_switch = KillSwitchState(active=True, triggered_at=now, reason=reason)
        self.emergency_stop = EmergencyStopState(active=True, triggered_at=now)

    @staticmethod
    def _parse_kill_switch(value: object) -> KillSwitchState:
        if not isinstance(value, dict) or type(value.get("active")) is not bool:
            raise ValueError("kill_switch must contain an exact boolean active field")
        parsed = KillSwitchState.model_validate(value)
        if parsed.active and (parsed.triggered_at is None or not (parsed.reason or "").strip()):
            raise ValueError("active kill_switch requires triggered_at and reason")
        return parsed

    @staticmethod
    def _parse_emergency_stop(value: object) -> EmergencyStopState:
        if not isinstance(value, dict) or type(value.get("active")) is not bool:
            raise ValueError("emergency_stop must contain an exact boolean active field")
        if "cancel_open_orders" in value and type(value.get("cancel_open_orders")) is not bool:
            raise ValueError("emergency_stop cancel_open_orders must be boolean")
        parsed = EmergencyStopState.model_validate(value)
        if parsed.active and parsed.triggered_at is None:
            raise ValueError("active emergency_stop requires triggered_at")
        return parsed

    def _load_risk_state(self, *, require_existing: bool = False) -> bool:
        if not self._state_path.exists():
            if require_existing:
                reason = "persisted risk state missing during safety refresh"
                self._activate_safety_controls_fail_closed(reason)
                self.persistence_error = f"FileNotFoundError: {reason}"
                return False
            return True
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("risk state must be a JSON object")

            migrated_legacy_controls = "kill_switch" not in data or "emergency_stop" not in data
            if migrated_legacy_controls:
                # Pre-v2 files never recorded stop controls. Their prior state
                # is unknowable, so migration latches both controls on instead
                # of silently assuming that trading was permitted.
                self._activate_safety_controls_fail_closed(
                    "legacy risk state lacked persisted safety controls; operator review required"
                )
            else:
                self.kill_switch = self._parse_kill_switch(data.get("kill_switch"))
                self.emergency_stop = self._parse_emergency_stop(data.get("emergency_stop"))

            self._daily_loss_date = str(data.get("utc_date") or self._daily_loss_date)
            raw_loss = data.get("daily_loss_cents", 0)
            if type(raw_loss) is not int or raw_loss < 0:
                raise ValueError("daily_loss_cents must be a non-negative integer")
            self._daily_loss_cents = raw_loss
            settlements = data.get("processed_settlement_ids", [])
            if not isinstance(settlements, list) or not all(isinstance(item, str) for item in settlements):
                raise ValueError("processed_settlement_ids must be a string list")
            self._processed_settlements = set(settlements[-10000:])
            self.persistence_error = None
            self._rollover_if_needed()
            if migrated_legacy_controls and not self._persist_risk_state():
                return False
            return True
        except Exception as exc:
            # An unreadable state is not equivalent to zero loss or inactive
            # safety controls. Both controls latch on in memory and the file is
            # quarantined until an operator repairs it.
            self._activate_safety_controls_fail_closed("persisted risk state unreadable")
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def _persist_risk_state(self) -> bool:
        if not self._persist_enabled:
            return True
        payload = {
            "utc_date": self._daily_loss_date,
            "daily_loss_cents": self._daily_loss_cents,
            "processed_settlement_ids": sorted(self._processed_settlements)[-10000:],
            "kill_switch": self.kill_switch.model_dump(mode="json"),
            "emergency_stop": self.emergency_stop.model_dump(mode="json"),
            "schema_version": RISK_STATE_SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self._state_path.with_name(
            f".{self._state_path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        )
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._state_path)
            self.persistence_error = None
            return True
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def verify_persistence(self) -> bool:
        """Prove the risk/safety sink is writable without erasing unknown state.

        An earlier load/write failure is a hard stop. In particular, a
        corrupt state file must never be overwritten with an optimistic zero
        merely because a pre-submit probe ran.
        """
        if self.persistence_error is not None:
            return False
        return self._persist_risk_state()

    def refresh_persisted_state(self) -> bool:
        """Reload persisted controls before a live submit.

        This closes the multi-process gap where an operator latches a stop in
        the dashboard process while a long-running executor still has a stale
        in-memory copy. A missing or unreadable file fails closed.
        """
        if not self._persist_enabled:
            return True
        return self._load_risk_state(require_existing=True)

    def record_realized_pnl(self, pnl_cents: int, *, settlement_id: str | None = None) -> bool:
        """Record one verified realized result; losses accumulate as positive cents.

        Returns False for a duplicate settlement id. Gains do not erase the
        daily loss cap, matching the conservative loss-limit semantics.
        """
        if self.persistence_error is not None:
            return False
        self._rollover_if_needed()
        identity = str(settlement_id) if settlement_id else None
        if identity and identity in self._processed_settlements:
            return False
        if identity:
            self._processed_settlements.add(identity)
        if int(pnl_cents) < 0:
            self._daily_loss_cents += -int(pnl_cents)
        return self._persist_risk_state()

    def set_mode(self, mode: AccountMode):
        self.mode = mode

    def enable_kill_switch(self, reason: str):
        self.kill_switch = KillSwitchState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
            reason=reason,
        )
        if self.persistence_error is not None:
            # Preserve the quarantined file; never overwrite unknown loss data.
            return False
        return self._persist_risk_state()

    def disable_kill_switch(self):
        if self.persistence_error is not None:
            self._activate_safety_controls_fail_closed(
                "cannot disable kill switch while persisted state is unhealthy"
            )
            return False
        previous = self.kill_switch
        self.kill_switch = KillSwitchState(active=False)
        if self._persist_risk_state():
            return True
        # The durable state still says active (or is unknowable); retain the
        # conservative in-memory latch if the deactivation write fails.
        self.kill_switch = previous if previous.active else KillSwitchState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
            reason="kill-switch deactivation persistence failed",
        )
        return False

    def trigger_emergency_stop(self):
        self.emergency_stop = EmergencyStopState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
        )
        if self.persistence_error is not None:
            return False
        return self._persist_risk_state()

    def clear_emergency_stop(self):
        """Persist an explicit operator reset; never auto-clear on restart."""
        if self.persistence_error is not None:
            self._activate_safety_controls_fail_closed(
                "cannot clear emergency stop while persisted state is unhealthy"
            )
            return False
        previous = self.emergency_stop
        self.emergency_stop = EmergencyStopState(active=False)
        if self._persist_risk_state():
            return True
        self.emergency_stop = previous if previous.active else EmergencyStopState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
        )
        return False

STATE = DummyState(persist=True)

# Compatibility alias for legacy pre-rename artifact readers.
DumbyState = DummyState
