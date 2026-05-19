"""Google Gemini provider implementation."""
from typing import Optional

from ai_providers.base import AIProvider, GenerationResult
from storage.asset_repo import get_api_key

# Pricing per 1M tokens (input, output)
_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash":       (0.10,  0.40),
    "gemini-1.5-flash":       (0.35,  1.05),
    "gemini-1.5-flash-8b":    (0.075, 0.30),
    "gemini-1.5-pro":         (3.50, 10.50),
}

_DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(AIProvider):
    provider_name = "gemini"

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
                error="Gemini API key not configured. Go to Settings to add it.",
            )
        try:
            import google.generativeai as genai  # lazy import
            genai.configure(api_key=api_key)

            # Build a single prompt string from messages (Gemini uses a different format)
            genai_model = genai.GenerativeModel(
                model_name=model,
                generation_config={"max_output_tokens": max_tokens},
            )

            # Convert message list to chat history
            history = []
            last_user_msg = ""
            system_instruction = ""
            for m in messages:
                if m["role"] == "system":
                    system_instruction = m["content"]
                elif m["role"] == "user":
                    last_user_msg = m["content"]
                    if history or not system_instruction:
                        history.append({"role": "user", "parts": [m["content"]]})
                elif m["role"] == "assistant":
                    history.append({"role": "model", "parts": [m["content"]]})

            # Prepend system instruction to first user message if present
            if system_instruction and history:
                first_user = next((h for h in history if h["role"] == "user"), None)
                if first_user:
                    first_user["parts"][0] = system_instruction + "\n\n" + first_user["parts"][0]
            elif system_instruction:
                last_user_msg = system_instruction + "\n\n" + last_user_msg

            chat = genai_model.start_chat(history=history[:-1] if len(history) > 1 else [])
            response = chat.send_message(history[-1]["parts"][0] if history else last_user_msg)

            content = response.text or ""
            tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
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

    def list_models(self) -> list[str]:
        return list(_PRICING.keys())

    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        model = model or _DEFAULT_MODEL
        price_in, _ = _PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens / 1_000_000) * price_in


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICING.get(model, (0.0, 0.0))
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
