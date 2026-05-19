"""Pre-generation cost estimation."""
from core.prompt_builder import estimate_token_count
from ai_providers.router import get_provider


def estimate(
    user_input: str,
    provider_name: str,
    model: str,
    history_length: int = 0,
) -> dict:
    """
    Returns a dict with:
      - tokens: estimated token count
      - cost_usd: estimated cost in USD
      - cost_display: formatted string like "$0.0012"
    """
    # Rough estimate: user input + avg history tokens
    base_tokens = estimate_token_count(user_input)
    history_tokens = history_length * 150  # avg 150 tokens per message
    total_tokens = base_tokens + history_tokens

    try:
        provider = get_provider(provider_name)
        cost = provider.estimate_cost(total_tokens, model)
    except Exception:
        cost = 0.0

    return {
        "tokens": total_tokens,
        "cost_usd": cost,
        "cost_display": f"~${cost:.4f}" if cost >= 0.0001 else "< $0.0001",
    }
