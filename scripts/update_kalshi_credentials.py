"""Update Dummy's Kalshi credentials from the Desktop info file.

Reads the desktop credential file, extracts the Key ID and private key, writes
the PEM to secrets/kalshi_private_key.pem, and updates the project .env file.
No secret values are printed.
"""
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_FILE = Path.home() / "Desktop" / "dummy api info.txt"
ENV_FILE = PROJECT_ROOT / ".env"
PEM_FILE = PROJECT_ROOT / "secrets" / "kalshi_private_key.pem"


def redact(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return f"*** (len={len(value)})"
    return f"{value[:3]}***{value[-3:]} (len={len(value)})"


def extract_key_id(text: str) -> str | None:
    # JSON object form
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in ("KALSHI_API_KEY_ID", "key_id", "keyID", "Key ID", "KEY ID"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    except Exception:
        pass

    # Label-driven extraction; value may be on the same line or the next non-empty line.
    lines = text.splitlines()
    looking_for_value = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        is_key_id_label = ("key id" in low or "key_id" in low or "api key" in low) and "private" not in low
        if is_key_id_label:
            for sep in (":", "="):
                if sep in stripped:
                    val = stripped.split(sep, 1)[1].strip().strip('"\'')
                    if val:
                        return val
            looking_for_value = True
            continue
        if looking_for_value:
            # Stop if we hit another obvious label before finding a value.
            if ":" in stripped or "=" in stripped or "key" in low:
                looking_for_value = False
                continue
            return stripped.strip('"\'')

    # Heuristic: Kalshi key IDs are typically 32-char hex or UUID-like strings.
    candidates = re.findall(r"\b([a-f0-9]{32}|[0-9a-fA-F-]{36})\b", text)
    if candidates:
        return candidates[0]
    return None


def extract_pem(text: str) -> str | None:
    # JSON object form
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in (
                "KALSHI_API_PRIVATE_KEY_PEM",
                "private_key",
                "privateKey",
                "Private Key",
                "PRIVATE KEY",
            ):
                v = data.get(k)
                if isinstance(v, str) and "BEGIN" in v:
                    return v.strip()
    except Exception:
        pass

    lines = text.splitlines()
    pem = []
    in_pem = False
    for line in lines:
        if "-----BEGIN" in line and "PRIVATE KEY-----" in line:
            in_pem = True
            pem.append(line.strip())
        elif in_pem:
            pem.append(line.strip())
            if "-----END" in line and "PRIVATE KEY-----" in line:
                break
    if pem:
        return "\n".join(pem)
    return None


def load_existing_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def main() -> int:
    if not DESKTOP_FILE.exists():
        print(f"Credential file not found: {DESKTOP_FILE}")
        return 1

    text = DESKTOP_FILE.read_text(encoding="utf-8", errors="replace")
    key_id = extract_key_id(text)
    pem = extract_pem(text)

    if not key_id:
        print("Could not locate KALSHI_API_KEY_ID in the desktop file.")
        return 1
    if not pem:
        print("Could not locate a private key PEM block in the desktop file.")
        return 1

    PEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEM_FILE.write_text(pem, encoding="utf-8")

    env = load_existing_env(ENV_FILE)
    env.update(
        {
            "KALSHI_API_KEY_ID": key_id,
            "KALSHI_API_PRIVATE_KEY_PEM_PATH": str(
                PEM_FILE.relative_to(PROJECT_ROOT).as_posix()
            ),
            "KALSHI_API_BASE": env.get("KALSHI_API_BASE", "https://api.elections.kalshi.com"),
            "KALSHI_API_VERSION": env.get("KALSHI_API_VERSION", "trade-api/v2"),
            "DUMMY_MODE": env.get("DUMMY_MODE", "OFF"),
            "DUMMY_LOG_LEVEL": env.get("DUMMY_LOG_LEVEL", "INFO"),
        }
    )
    # Do not store the inline PEM in .env when we already reference the PEM file.
    env.pop("KALSHI_API_PRIVATE_KEY_PEM", None)

    ENV_FILE.write_text(
        "\n".join(f"{k}={v}" for k, v in env.items()) + "\n",
        encoding="utf-8",
    )

    print("Credentials updated successfully.")
    print(f"  PEM file: {PEM_FILE.relative_to(PROJECT_ROOT)}")
    print(f"  Key ID set: {redact(key_id)}")
    print(f"  PEM lines: {len(pem.splitlines())}")
    print(f"  .env file: {ENV_FILE.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
