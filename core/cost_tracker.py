"""Cost tracking — logs every generation to usage_logs."""
from storage.asset_repo import log_usage, get_total_cost, get_usage_summary
from ai_providers.base import GenerationResult


def track(result: GenerationResult, project_id: str = "", generation_type: str = "chat") -> None:
    """Persist a GenerationResult to usage_logs."""
    if result.ok:
        log_usage(
            provider=result.provider,
            model=result.model,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            cost=result.cost,
            project_id=project_id,
            generation_type=generation_type,
        )


def total_cost(project_id: str = "") -> float:
    return get_total_cost(project_id or None)


def usage_summary() -> list[dict]:
    return get_usage_summary()
