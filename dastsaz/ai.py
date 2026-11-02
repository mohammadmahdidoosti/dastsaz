"""One small helper for the AI calls that return JSON (OpenRouter). Text sent to the model is data, not orders."""
from __future__ import annotations

import json
import logging
import re

import requests

from . import config as C
from .analyze import OPENROUTER

log = logging.getLogger(__name__)


def ask_json(prompt: str, data, key: str, max_tokens: int = 4000, model: str | None = None) -> tuple[dict, float]:
    """({} on failure, cost in dollars)."""
    if not key:
        return {}, 0.0
    body = {"model": model or C.AI_MODEL, "max_tokens": max_tokens, "temperature": 0, "reasoning": {"enabled": False},
            "messages": [{"role": "user", "content": prompt + "\n\n" + json.dumps(data, ensure_ascii=False)}]}
    try:
        r = requests.post(OPENROUTER, json=body, timeout=240, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Dastsaz trends"})
        j = r.json()
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        return _parse(txt), float((j.get("usage") or {}).get("cost") or 0)
    except Exception as e:  # noqa: BLE001
        log.warning("AI call failed: %s", e)
        return {}, 0.0


def _parse(txt: str) -> dict:
    """JSON from the model's text; if the answer was cut or slightly broken, keep the complete items."""
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return {}
    raw = m.group(0)
    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError:
        pass
    # cut back to the last complete object inside the first list and close it
    for k in range(len(raw) - 1, 0, -1):
        if raw[k] == "}":
            try:
                return json.loads(raw[:k + 1] + "]}", strict=False)
            except json.JSONDecodeError:
                continue
    log.warning("AI answer was not readable JSON")
    return {}
