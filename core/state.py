from datetime import datetime, timezone
from core.ontology import AccountMode, KillSwitchState, EmergencyStopState

class DumbyState:
    def __init__(self):
        self.mode = AccountMode.OFF
        self.kill_switch = KillSwitchState(active=False)
        self.emergency_stop = EmergencyStopState(active=False)
        self.kalshi_connected = False
        self.balance_cents = 0
        self.daily_loss_cents = 0
        self.daily_loss_window_start = datetime.now(timezone.utc)

    def set_mode(self, mode: AccountMode):
        self.mode = mode

    def enable_kill_switch(self, reason: str):
        self.kill_switch = KillSwitchState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
            reason=reason,
        )

    def disable_kill_switch(self):
        self.kill_switch = KillSwitchState(active=False)

    def trigger_emergency_stop(self):
        self.emergency_stop = EmergencyStopState(
            active=True,
            triggered_at=datetime.now(timezone.utc),
        )

STATE = DumbyState()
