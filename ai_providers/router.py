"""Provider registry and factory."""
from typing import Optional

from ai_providers.base import AIProvider
from ai_providers.openai_provider import OpenAIProvider
from ai_providers.claude_provider import ClaudeProvider
from ai_providers.gemini_provider import GeminiProvider
from ai_providers.ollama_provider import OllamaProvider

_REGISTRY: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

# Singleton instances (one per provider)
_instances: dict[str, AIProvider] = {}


def get_provider(name: str) -> AIProvider:
    """Return a singleton provider instance by name."""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider: {name!r}. Available: {list(_REGISTRY)}")
    if name not in _instances:
        _instances[name] = _REGISTRY[name]()
    return _instances[name]


def list_providers() -> list[str]:
    return list(_REGISTRY.keys())


def get_configured_providers() -> list[str]:
    """Return providers that have API keys stored."""
    return [name for name in _REGISTRY if get_provider(name).is_configured()]


def get_models_for_provider(provider_name: str) -> list[str]:
    return get_provider(provider_name).list_models()


def cheapest_provider() -> Optional[str]:
    """Return the provider with the cheapest default model cost (per 1K tokens)."""
    best = None
    best_cost = float("inf")
    for name in list_providers():
        p = get_provider(name)
        if not p.is_configured():
            continue
        cost = p.estimate_cost(1000)
        if cost < best_cost:
            best_cost = cost
            best = name
    return best
