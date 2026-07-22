import os
import base64
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

def _kalshi_base() -> str:
    return os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")


def _kalshi_version() -> str:
    return os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")


# Backward-compatible module-level aliases for code that reads them at import time.
BASE = _kalshi_base()
VERSION = _kalshi_version()


def load_private_key():
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM", "") or os.environ.get(
        "KALSHI_API_PRIVATE_KEY", ""
    )
    if not pem:
        pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH", "")
        if pem_path and Path(pem_path).exists():
            pem = Path(pem_path).read_text()
    if not pem:
        raise RuntimeError("Kalshi private key not configured")
    return serialization.load_pem_private_key(pem.encode(), password=None)


def sign_request(method: str, path: str, body: str = "") -> dict:
    """Sign a Kalshi API request using RSA-PSS SHA-256.

    The signed message is ``{timestamp_ms}{METHOD}{full_path}`` where
    ``full_path`` includes the API version prefix (e.g.
    ``/trade-api/v2/account``) and excludes query strings.  This matches the
    current Kalshi v2 authentication specification.
    """
    del body  # Kalshi v2 does not include the request body in the signature.
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if not key_id:
        raise RuntimeError("KALSHI_API_KEY_ID not set")

    ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    full_path = path.split("?")[0]
    version_prefix = f"/{_kalshi_version()}"
    if not full_path.startswith(version_prefix):
        full_path = f"{version_prefix}{full_path}"

    msg = f"{ts}{method.upper()}{full_path}"
    sig = load_private_key().sign(
        msg.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }
