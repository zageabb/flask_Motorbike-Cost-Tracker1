from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INSTANCE_DIR = ROOT / "instance"
AUTH_SECRET_FILE = INSTANCE_DIR / "auth_secret_key"
SETTINGS_FILE = ROOT / "settings.json"
LOCK = threading.Lock()

# This is a small, private LAN application. Keep authenticated users signed in
# unless they explicitly sign out. The Flask app still refreshes the expiry on
# each request.
MIN_AUTH_SESSION_DAYS = 3650


def _read_secret_file() -> str | None:
    try:
        value = AUTH_SECRET_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _persistent_auth_secret() -> str:
    """Return one stable Flask signing key across restarts and deployments.

    AUTH_SECRET_KEY remains an explicit override. Otherwise the first process
    creates instance/auth_secret_key and every later process reuses it. This
    prevents authenticated cookies becoming invalid when a launcher or service
    supplies a changing SECRET_KEY on restart.
    """
    explicit = os.environ.get("AUTH_SECRET_KEY", "").strip()
    if explicit:
        return explicit

    stored = _read_secret_file()
    if stored:
        return stored

    try:
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last-resort compatibility fallback. The repository already ignores
        # instance/, so normal deployments should always use the file above.
        return os.environ.get("SECRET_KEY", "dev-secret-key")

    candidate = os.environ.get("SECRET_KEY", "").strip() or secrets.token_hex(32)
    try:
        descriptor = os.open(
            AUTH_SECRET_FILE,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(candidate + "\n")
        return candidate
    except FileExistsError:
        # Multiple workers may start together. The first one creates the file;
        # the others immediately reuse it.
        return _read_secret_file() or candidate
    except OSError:
        return candidate


def _configure_auth_environment() -> None:
    os.environ["SECRET_KEY"] = _persistent_auth_secret()

    try:
        configured_days = int(os.environ.get("AUTH_SESSION_DAYS", "0"))
    except ValueError:
        configured_days = 0
    if configured_days < MIN_AUTH_SESSION_DAYS:
        os.environ["AUTH_SESSION_DAYS"] = str(MIN_AUTH_SESSION_DAYS)


_configure_auth_environment()


DEFAULTS = {
    "ollama_url": "http://127.0.0.1:11434",
    "model": "llama3.2",
    "assistant_instructions": (
        "You are a careful motorbike portfolio assistant. Use only the supplied portfolio "
        "data for factual answers. Never invent prices, purchases, sales, or record identifiers."
    ),
}


def get_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return dict(DEFAULTS)
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save_settings(values: dict) -> dict:
    current = get_settings()
    for key in DEFAULTS:
        if key in values:
            current[key] = str(values[key]).strip()
    current["ollama_url"] = current["ollama_url"].rstrip("/")
    with LOCK:
        SETTINGS_FILE.write_text(json.dumps(current, indent=2) + "\n")
    return current
