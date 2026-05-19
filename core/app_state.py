"""Global application state shared across all UI components."""
from typing import Optional, Callable

from storage.models import Project, Chat, Message, Asset
from storage.project_repo import get_all_projects
from storage.chat_repo import get_chats_for_project


class AppState:
    """Single source of truth for runtime state. No persistence here — that lives in the DB."""

    def __init__(self):
        self.projects: list[Project] = []
        self.current_project: Optional[Project] = None
        self.current_chat: Optional[Chat] = None
        self.messages: list[Message] = []
        self.chats: list[Chat] = []          # chats for current project
        self.assets: list[Asset] = []

        self.current_view: str = "chat"       # chat | assets | settings
        self.selected_provider: str = "openai"
        self.selected_model: str = "gpt-4o-mini"
        self.generation_type: str = "chat"    # chat | ad_copy | image_prompt | video_prompt | bulk

        self.is_generating: bool = False

        # UI callbacks — views register here to react to state changes
        self._on_projects_changed: list[Callable] = []
        self._on_chat_changed: list[Callable] = []
        self._on_project_selected: list[Callable] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def load_initial_data(self) -> None:
        self.projects = get_all_projects()

    # ── Subscriptions ──────────────────────────────────────────────────────────

    def subscribe_projects(self, cb: Callable) -> None:
        self._on_projects_changed.append(cb)

    def subscribe_chat(self, cb: Callable) -> None:
        self._on_chat_changed.append(cb)

    def subscribe_project_selected(self, cb: Callable) -> None:
        self._on_project_selected.append(cb)

    # ── Mutations ──────────────────────────────────────────────────────────────

    def set_projects(self, projects: list[Project]) -> None:
        self.projects = projects
        for cb in self._on_projects_changed:
            cb()

    def select_project(self, project: Optional[Project]) -> None:
        self.current_project = project
        if project:
            self.chats = get_chats_for_project(project.id)
        else:
            self.chats = []
        self.current_chat = self.chats[0] if self.chats else None
        for cb in self._on_project_selected:
            cb()

    def select_chat(self, chat: Chat) -> None:
        self.current_chat = chat
        for cb in self._on_chat_changed:
            cb()

    def refresh_projects(self) -> None:
        self.projects = get_all_projects()
        for cb in self._on_projects_changed:
            cb()

    def refresh_chats(self) -> None:
        if self.current_project:
            self.chats = get_chats_for_project(self.current_project.id)
