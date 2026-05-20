"""Main application layout — 3-panel design."""
import flet as ft

from core.app_state import AppState
from ui import theme as T
from ui.sidebar import Sidebar
from ui.chat_view import ChatView
from ui.project_view import RightPanel
from ui.asset_view import AssetView
from ui.settings_view import SettingsView
from ui.brief_view import BriefView
from ui.brand_view import BrandView
from storage.project_repo import get_project


class AppLayout:
    """Root layout: sidebar | main area | right panel."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.state = AppState()
        self.state.load_initial_data()

        # Instantiate persistent view components
        self.sidebar = Sidebar(page=page, app=self)
        self.chat_view = ChatView(page=page, app=self)
        self.right_panel = RightPanel(page=page, app=self)

        # Swappable main content area
        self._main_area = ft.Container(expand=True, bgcolor=T.BG_PRIMARY)

    # ── Entry ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Column:
        # Pre-select first project if available
        if self.state.projects:
            self.state.select_project(self.state.projects[0])

        sidebar_ctrl = self.sidebar.build()
        right_panel_ctrl = self.right_panel.build()
        self._main_area.content = self.chat_view.build()

        # Check if user needs to configure API keys (first-run hint)
        self._maybe_show_welcome()

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        sidebar_ctrl,
                        T.divider(vertical=True),
                        self._main_area,
                        T.divider(vertical=True),
                        right_panel_ctrl,
                    ],
                    expand=True,
                    spacing=0,
                )
            ],
            spacing=0,
            expand=True,
        )

    # ── Navigation ─────────────────────────────────────────────────────────────

    def show_chat_view(self) -> None:
        self.state.current_view = "chat"
        self._main_area.content = self.chat_view.build()
        self.chat_view.on_project_changed()
        self.right_panel.refresh()
        self._main_area.update()

    def show_assets_view(self) -> None:
        self.state.current_view = "assets"
        asset_view = AssetView(page=self.page, app=self)
        self._main_area.content = asset_view.build()
        self._main_area.update()

    def show_settings_view(self) -> None:
        self.state.current_view = "settings"
        settings_view = SettingsView(page=self.page, app=self)
        self._main_area.content = settings_view.build()
        self._main_area.update()

    def show_brand_view(self) -> None:
        self.state.current_view = "brand"
        if self.state.current_project:
            from storage.project_repo import get_project as _gp
            fresh = _gp(self.state.current_project.id)
            if fresh:
                self.state.current_project = fresh
        brand_view = BrandView(page=self.page, app=self)
        self._main_area.content = brand_view.build()
        self._main_area.update()

    def show_brief_view(self) -> None:
        self.state.current_view = "brief"
        # Always reload from DB so the page reflects the latest saved data
        if self.state.current_project:
            fresh = get_project(self.state.current_project.id)
            if fresh:
                self.state.current_project = fresh
        brief_view = BriefView(page=self.page, app=self)
        self._main_area.content = brief_view.build()
        self._main_area.update()

    def refresh_brief_if_active(self) -> None:
        if self.state.current_view == "brief":
            self.show_brief_view()

    # ── Refresh hooks ──────────────────────────────────────────────────────────

    def refresh_right_panel(self) -> None:
        self.right_panel.refresh()

    def refresh_sidebar(self) -> None:
        self.sidebar.refresh()

    # ── First-run ──────────────────────────────────────────────────────────────

    def _maybe_show_welcome(self) -> None:
        from storage.asset_repo import get_all_api_keys
        keys = get_all_api_keys()
        if not keys:
            # Show a non-blocking banner prompting the user to add an API key
            def go_to_settings(e):
                self.page.banner.open = False
                self.page.update()
                self.show_settings_view()
                self.sidebar.refresh()

            def dismiss(e):
                self.page.banner.open = False
                self.page.update()

            self.page.banner = ft.Banner(
                bgcolor="#1a1a2e",
                leading=ft.Icon(ft.Icons.KEY_OUTLINED, color=T.WARNING, size=28),
                content=ft.Text(
                    "No API keys configured. Add an OpenAI, Claude, or Gemini key to start generating.",
                    color=T.TEXT_PRIMARY,
                    size=13,
                ),
                actions=[
                    ft.TextButton("Open Settings", on_click=go_to_settings, style=ft.ButtonStyle(color=T.ACCENT_LIGHT)),
                    ft.TextButton("Dismiss", on_click=dismiss, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                ],
                force_actions_below=False,
            )
            self.page.banner.open = True
