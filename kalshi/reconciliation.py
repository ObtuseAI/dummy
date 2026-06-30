from typing import Any

def reconcile_orders(local: list[dict], remote: list[dict]) -> dict:
    remote_ids = {o["order_id"] for o in remote}
    local_ids = {o["order_id"] for o in local}
    return {
        "missing_local": list(remote_ids - local_ids),
        "missing_remote": list(local_ids - remote_ids),
        "matched": list(local_ids & remote_ids),
    }

def reconcile_fills(local: list[dict], remote: list[dict]) -> dict:
    remote_ids = {f["fill_id"] for f in remote}
    local_ids = {f["fill_id"] for f in local}
    return {
        "missing_local": list(remote_ids - local_ids),
        "matched": list(local_ids & remote_ids),
    }
