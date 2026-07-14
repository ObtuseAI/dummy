import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROOF_DIR = Path(__file__).parent


def write_proof(component: str, verdict: str, payload: dict) -> str:
    ref_id = str(uuid.uuid4())
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    bundle = {
        "ref_id": ref_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "verdict": verdict,
        "payload_hash": payload_hash,
        "payload": payload,
    }
    path = PROOF_DIR / f"{ref_id}.json"
    path.write_text(json.dumps(bundle, indent=2, default=str))
    return ref_id


def list_proofs():
    return [p.stem for p in PROOF_DIR.glob("*.json")]
