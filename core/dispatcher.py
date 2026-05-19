"""Dispatcher — orchestrates AI calls via the provider router."""
from typing import Optional

from ai_providers.base import GenerationResult
from ai_providers.router import get_provider
from core.app_state import AppState
from core import cost_tracker
from core.prompt_builder import build_messages
from storage.chat_repo import add_message, get_messages
from storage.models import Message


def generate(
    state: AppState,
    user_input: str,
    file_context: str = "",
) -> GenerationResult:
    """
    Full generation pipeline:
      1. Build messages with brand context
      2. Call the selected provider
      3. Persist messages to DB
      4. Track cost
      5. Return the result
    """
    provider = get_provider(state.selected_provider)

    # Ensure we have a chat
    if state.current_chat is None:
        from storage.chat_repo import create_chat
        project_id = state.current_project.id if state.current_project else None
        state.current_chat = create_chat(project_id=project_id)
        state.refresh_chats()

    # Load history from DB
    history: list[Message] = get_messages(state.current_chat.id)

    # Build prompt
    messages = build_messages(
        user_input=user_input,
        history=history,
        project=state.current_project,
        generation_type=state.generation_type,
        file_context=file_context,
    )

    # Call AI
    result = provider.generate(messages=messages, model=state.selected_model)

    # Persist user message
    add_message(
        chat_id=state.current_chat.id,
        role="user",
        content=user_input,
    )

    if result.ok:
        # Persist AI response
        add_message(
            chat_id=state.current_chat.id,
            role="assistant",
            content=result.content,
            provider=result.provider,
            model=result.model,
            tokens_used=result.tokens_input + result.tokens_output,
            cost=result.cost,
        )
        # Track cost
        project_id = state.current_project.id if state.current_project else ""
        cost_tracker.track(result, project_id=project_id, generation_type=state.generation_type)

    return result
