import os, base64
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

def load_private_key():
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM", "")
    if not pem:
        pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH", "")
        if pem_path and Path(pem_path).exists():
            pem = Path(pem_path).read_text()
    if not pem:
        raise RuntimeError("Kalshi private key not configured")
    return serialization.load_pem_private_key(pem.encode(), password=None)

def sign_request(method: str, path: str, body: str = "") -> dict:
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if not key_id:
        raise RuntimeError("KALSHI_API_KEY_ID not set")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    msg = f"{ts}{method}{path}{body}"
    sig = load_private_key().sign(msg.encode(), padding.PKCS1v15(), hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }
