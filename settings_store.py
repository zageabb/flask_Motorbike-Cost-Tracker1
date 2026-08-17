from __future__ import annotations

import json
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / "settings.json"
LOCK = threading.Lock()

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
