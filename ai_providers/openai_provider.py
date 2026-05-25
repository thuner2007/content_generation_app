"""OpenAI provider implementation."""
from typing import Optional

from ai_providers.base import AIProvider, GenerationResult
from storage.asset_repo import get_api_key

# Pricing per 1M tokens (input, output) as of May 2026
_PRICING: dict[str, tuple[float, float]] = {
    # GPT-4.1 series (April 2025) — best coding + instruction following, 1M context
    "gpt-4.1":             (2.00,   8.00),
    "gpt-4.1-mini":        (0.40,   1.60),
    "gpt-4.1-nano":        (0.10,   0.40),
    # Reasoning models (o-series)
    "o3":                  (10.00, 40.00),
    "o4-mini":             (1.10,   4.40),
    "o3-pro":              (20.00, 80.00),
    # GPT-4o series (still supported)
    "gpt-4o":              (2.50,  10.00),
    "gpt-4o-mini":         (0.15,   0.60),
    # Legacy
    "o1":                  (15.00, 60.00),
    "o1-mini":             (3.00,  12.00),
}

_DEFAULT_MODEL = "gpt-4.1-mini"


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
        images: Optional[list[dict]] = None,
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

            send_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

            # Attach images to last user message (vision)
            if images:
                for i in range(len(send_messages) - 1, -1, -1):
                    if send_messages[i]["role"] == "user":
                        content = [{"type": "text", "text": send_messages[i]["content"]}]
                        for img in images:
                            url = f"data:{img['mime_type']};base64,{img['base64']}"
                            content.append({"type": "image_url", "image_url": {"url": url}})
                        send_messages[i]["content"] = content
                        break

            response = client.chat.completions.create(
                model=model,
                messages=send_messages,
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

    # o-series and GPT-4.1 reasoning models are vision-capable; o1/o3 text-only
    _VISION_MODELS = {"gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"}

    def supports_vision(self, model: Optional[str] = None) -> bool:
        return (model or _DEFAULT_MODEL) in self._VISION_MODELS

    def list_models(self) -> list[str]:
        return list(_PRICING.keys())

    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        model = model or _DEFAULT_MODEL
        price_in, _ = _PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens / 1_000_000) * price_in


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICING.get(model, (0.0, 0.0))
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
