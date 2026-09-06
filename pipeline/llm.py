"""The API boundary: one function makes every model call, disk-cached in data/cache/.

A committed cache means the repo re-runs extraction with zero API calls; only a prompt
or data change (which changes the cache key) touches the API again.
"""

import hashlib
import json
import os
import re
from pathlib import Path

from .prompts import PROMPT_VERSION

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set and no cached result exists for this call.\n"
                "Export the key to run extraction; cached runs need no key.")
        _client = anthropic.Anthropic()
    return _client


def cache_key(model, prompt):
    payload = f"{model}\n{PROMPT_VERSION}\n{prompt}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _parse_json(text):
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def _call(model, prompt):
    resp = _get_client().messages.create(
        model=model, max_tokens=2000, temperature=0,
        messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text


def complete(model, prompt, required_keys=()):
    """Return the model's JSON answer for prompt, from cache when possible."""
    key = cache_key(model, prompt)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())

    text = _call(model, prompt)
    try:
        result = _parse_json(text)
    except json.JSONDecodeError as err:
        retry = f"{prompt}\n\nYour previous answer failed to parse as JSON ({err}). Answer again with ONLY valid JSON."
        result = _parse_json(_call(model, retry))

    for k in required_keys:
        result.setdefault(k, [])
    path.write_text(json.dumps(result, indent=2))
    return result
