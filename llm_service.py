from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    pass


def _request(url: str, *, payload: dict | None = None, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f"Ollama request failed: {exc}") from exc


def list_models(settings: dict) -> list[str]:
    result = _request(f"{settings['ollama_url']}/api/tags", timeout=10)
    return [item["name"] for item in result.get("models", []) if item.get("name")]


def _json_object(value: str) -> dict:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise LLMError("The model did not return valid structured data.") from exc
    if not isinstance(result, dict):
        raise LLMError("The model returned an unexpected response shape.")
    return result


def ask_assistant(query: str, portfolio: dict, settings: dict) -> dict:
    schema = {
        "reply": "Answer or concise explanation of the proposed changes",
        "actions": [
            {
                "type": "create_motorbike | add_part | update_motorbike",
                "motorbike_id": "required existing integer for add/update",
                "name": "motorbike name for create/update",
                "purchase_price": "number for create/update",
                "tanya_contribution": "number for create/update",
                "gerald_contribution": "number for create/update",
                "buyer": "Tanya, Gerald, shared, or other",
                "is_sold": "boolean for create/update",
                "sale_price": "number or null for create/update",
                "ignore": "boolean for create/update",
                "description": "part/equipment description for add_part",
                "source": "supplier/source for add_part",
                "cost": "number for add_part",
                "purchased_on": "YYYY-MM-DD or null for add_part",
            }
        ],
    }
    system = (
        settings["assistant_instructions"]
        + "\nReturn JSON only using this shape: "
        + json.dumps(schema)
        + "\nUse actions=[] for questions and analysis. Propose actions only when the user asks "
        "to create or change data. Never propose deletion. A part means equipment, component, "
        "service, consumable, or other bike-related cost. Preserve exact existing motorbike IDs."
    )
    result = _request(
        f"{settings['ollama_url']}/api/chat",
        payload={
            "model": settings["model"],
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Portfolio data:\n{json.dumps(portfolio)}\n\nRequest:\n{query}"},
            ],
        },
    )
    content = result.get("message", {}).get("content", "")
    return _json_object(content)
