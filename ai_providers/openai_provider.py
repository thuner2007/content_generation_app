"""OpenAI provider implementation."""
from typing import Optional

from ai_providers.base import AIProvider, GenerationResult
from storage.asset_repo import get_api_key

# Pricing per 1M tokens (input, output) as of mid-2025
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":              (2.50,  10.00),
    "gpt-4o-mini":         (0.15,   0.60),
    "gpt-4-turbo":         (10.00, 30.00),
    "gpt-3.5-turbo":       (0.50,   1.50),
    "o1":                  (15.00, 60.00),
    "o1-mini":             (3.00,  12.00),
}

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        model = model or _DEFAULT_MODEL
        api_key = get_api_key(self.provider_name)
        if not api_key:
            return GenerationResult(
                content="",
                model=model,
                provider=self.provider_name,
                error="OpenAI API key not configured. Go to Settings to add it.",
            )
        try:
            from openai import OpenAI  # lazy import so app loads without the package
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            usage = response.usage
            tokens_in = usage.prompt_tokens if usage else 0
            tokens_out = usage.completion_tokens if usage else 0
            cost = _calculate_cost(model, tokens_in, tokens_out)
            return GenerationResult(
                content=choice.message.content or "",
                model=model,
                provider=self.provider_name,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost=cost,
            )
        except Exception as exc:
            return GenerationResult(
                content="",
                model=model,
                provider=self.provider_name,
                error=str(exc),
            )

    def list_models(self) -> list[str]:
        return list(_PRICING.keys())

    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        model = model or _DEFAULT_MODEL
        price_in, _ = _PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens / 1_000_000) * price_in


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICING.get(model, (0.0, 0.0))
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
