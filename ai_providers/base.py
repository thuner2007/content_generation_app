"""Abstract base class that every AI provider must implement."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GenerationResult:
    content: str
    model: str
    provider: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost: float = 0.0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class AIProvider(ABC):
    """Interface every provider must implement."""

    provider_name: str = "base"

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        """Generate a response. messages = [{'role': ..., 'content': ...}]"""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return available model identifiers."""

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        """Rough USD cost estimate for prompt_tokens (input only, no output)."""

    def default_model(self) -> str:
        models = self.list_models()
        return models[0] if models else ""

    def is_configured(self) -> bool:
        from storage.asset_repo import get_api_key
        key = get_api_key(self.provider_name)
        return bool(key and key.strip())
