"""Anthropic Claude provider implementation."""
from typing import Optional

from ai_providers.base import AIProvider, GenerationResult
from storage.asset_repo import get_api_key

# Pricing per 1M tokens (input, output)
_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-20241022": (3.00,  15.00),
    "claude-3-5-haiku-20241022":  (0.80,   4.00),
    "claude-3-opus-20240229":     (15.00, 75.00),
    "claude-3-haiku-20240307":    (0.25,   1.25),
}

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"


class ClaudeProvider(AIProvider):
    provider_name = "claude"

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
                error="Claude API key not configured. Go to Settings to add it.",
            )
        try:
            import anthropic  # lazy import
            client = anthropic.Anthropic(api_key=api_key)

            # Separate system message if present
            system_content = ""
            chat_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_content = m["content"]
                else:
                    chat_messages.append({"role": m["role"], "content": m["content"]})

            # Attach images to last user message (vision)
            if images:
                for i in range(len(chat_messages) - 1, -1, -1):
                    if chat_messages[i]["role"] == "user":
                        content = [{"type": "text", "text": chat_messages[i]["content"]}]
                        for img in images:
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": img["mime_type"],
                                    "data": img["base64"],
                                },
                            })
                        chat_messages[i]["content"] = content
                        break

            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                messages=chat_messages,
            )
            if system_content:
                kwargs["system"] = system_content

            response = client.messages.create(**kwargs)
            content = response.content[0].text if response.content else ""
            tokens_in = response.usage.input_tokens if response.usage else 0
            tokens_out = response.usage.output_tokens if response.usage else 0
            cost = _calculate_cost(model, tokens_in, tokens_out)
            return GenerationResult(
                content=content,
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

    def supports_vision(self, model: Optional[str] = None) -> bool:
        return True  # all Claude 3 models support vision

    def list_models(self) -> list[str]:
        return list(_PRICING.keys())

    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        model = model or _DEFAULT_MODEL
        price_in, _ = _PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens / 1_000_000) * price_in


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICING.get(model, (0.0, 0.0))
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
