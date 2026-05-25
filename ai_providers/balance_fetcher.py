"""Fetches remaining credit / balance from AI provider APIs.

Only providers that expose a public balance endpoint are supported.
Others silently return None so the UI hides the widget.
"""
import json
import time
import urllib.request
import urllib.error
from typing import Optional

# Cache: provider -> (timestamp, balance_string | None)
_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_CACHE_TTL = 300.0  # 5 minutes — avoid hammering APIs


def fetch_balance(provider: str) -> Optional[str]:
    """Return a formatted balance string (e.g. '$4.20') or None if unavailable."""
    now = time.time()
    cached = _CACHE.get(provider)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    result = _do_fetch(provider)
    _CACHE[provider] = (now, result)
    return result


def invalidate(provider: str) -> None:
    """Force next call to re-fetch (e.g. after API key change)."""
    _CACHE.pop(provider, None)


# ── Per-provider fetchers ──────────────────────────────────────────────────────

def _do_fetch(provider: str) -> Optional[str]:
    from storage.asset_repo import get_api_key
    api_key = get_api_key(provider)
    if not api_key or not api_key.strip():
        return None

    if provider == "openai":
        return _fetch_openai(api_key.strip())
    # Anthropic, Gemini, Ollama do not expose a public balance endpoint
    return None


def _fetch_openai(api_key: str) -> Optional[str]:
    """Fetch available credit balance from OpenAI's organization balance endpoint."""
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/organization/balance",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())

        available = data.get("available", [])
        if available:
            amount = float(available[0].get("amount", 0))
            if amount >= 1000:
                # likely reported in cents
                amount /= 100
            return f"${amount:.2f}"
        return None
    except urllib.error.HTTPError as exc:
        # 403 = key lacks billing scope, 404 = endpoint not available on this account type
        if exc.code in (401, 403, 404):
            return None
        return None
    except Exception:
        return None
