"""Right panel: quick action tools + fixed cost bar."""
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage import asset_repo
from core.app_state import AppState

if TYPE_CHECKING:
    from ui.layout import AppLayout


class RightPanel:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state: AppState = app.state

        self._tools_area: ft.Container | None = None
        self._container: ft.Container | None = None

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Container:
        self._collapsed = False
        self._tools_area = ft.Container(expand=True, content=self._build_tools_section())
        self._cost_bar = self._build_cost_bar()

        self._container = ft.Container(
            content=self._build_expanded_content(),
            width=T.PANEL_WIDTH,
            bgcolor=T.BG_SIDEBAR,
            padding=0,
        )
        return self._container

    def _build_expanded_content(self) -> ft.Column:
        return ft.Column(
            controls=[
                self._tools_area,
                T.divider(),
                self._cost_bar,
            ],
            spacing=0,
            expand=True,
        )

    def _build_collapsed_strip(self) -> ft.Column:
        return ft.Column(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT,
                    tooltip="Show Quick Launch",
                    on_click=lambda e: self._toggle_panel(),
                    icon_color=T.TEXT_MUTED,
                    icon_size=16,
                    style=ft.ButtonStyle(
                        overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _toggle_panel(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._container.width = 28
            self._container.content = self._build_collapsed_strip()
        else:
            self._tools_area.content = self._build_tools_section()
            self._container.width = T.PANEL_WIDTH
            self._container.content = self._build_expanded_content()
        self._container.update()

    # ── Section builders ───────────────────────────────────────────────────────

    def _build_tools_section(self) -> ft.Column:
        tools = [
            ("Write Ad Copy", ft.Icons.TEXT_FIELDS, "ad_copy",
             "Facebook / Google / Instagram ad headlines and primary text"),
            ("Image Prompts", ft.Icons.IMAGE_OUTLINED, "image_prompt",
             "Detailed prompts for Midjourney, DALL-E, Stable Diffusion"),
            ("Video Prompts", ft.Icons.MOVIE_OUTLINED, "video_prompt",
             "Cinematic prompts for Kling, Sora, or Runway"),
            ("10 Variations", ft.Icons.FORMAT_LIST_BULLETED, "bulk",
             "Generate 10 distinct ad copy variations for A/B testing"),
            ("Product Ideas", ft.Icons.LIGHTBULB_OUTLINE, "product_ideas",
             "Creative marketing angles and campaign concepts"),
        ]
        tool_cards = []
        for label, icon, gtype, desc in tools:
            tool_cards.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon, size=16, color=T.ACCENT_LIGHT),
                                width=32,
                                height=32,
                                bgcolor=T.ACCENT_DIM,
                                border_radius=8,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(label, size=13, color=T.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                                    ft.Text(desc, size=11, color=T.TEXT_MUTED),
                                ],
                                spacing=2,
                                tight=True,
                                expand=True,
                            ),
                            ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=12, color=T.TEXT_MUTED),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=12),
                    bgcolor=T.BG_CARD,
                    border_radius=10,
                    border=ft.border.all(1, T.BORDER),
                    on_click=lambda e, g=gtype: self._launch_tool(g),
                    ink=True,
                )
            )

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text("Quick Launch", size=12, weight=ft.FontWeight.W_600,
                                    color=T.TEXT_MUTED, style=ft.TextStyle(letter_spacing=1.0)),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_RIGHT,
                                tooltip="Hide panel",
                                on_click=lambda e: self._toggle_panel(),
                                icon_color=T.TEXT_MUTED,
                                icon_size=16,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                    padding=ft.padding.all(4),
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.only(left=14, top=10, bottom=4, right=4),
                ),
                ft.Container(
                    content=ft.Column(controls=tool_cards, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
                    padding=ft.padding.symmetric(horizontal=10),
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        )

    def _build_cost_bar(self) -> ft.Container:
        total = asset_repo.get_total_cost()
        project_cost = 0.0
        if self.state.current_project:
            project_cost = asset_repo.get_total_cost(self.state.current_project.id)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.ATTACH_MONEY, size=14, color=T.TEXT_MUTED),
                                ft.Text("Cost", size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600),
                                ft.Container(expand=True),
                                ft.Column(
                                    controls=[
                                        ft.Text(f"${total:.4f}", size=12, color=T.ACCENT_LIGHT, weight=ft.FontWeight.W_600),
                                        ft.Text("total", size=10, color=T.TEXT_MUTED),
                                    ],
                                    spacing=0,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    tight=True,
                                ),
                                ft.Container(width=16),
                                ft.Column(
                                    controls=[
                                        ft.Text(f"${project_cost:.4f}", size=12, color=T.SUCCESS, weight=ft.FontWeight.W_600),
                                        ft.Text("project", size=10, color=T.TEXT_MUTED),
                                    ],
                                    spacing=0,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    tight=True,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=14, vertical=12),
                    ),
                ],
                spacing=0,
            ),
            bgcolor=T.BG_SIDEBAR,
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def _launch_tool(self, gtype: str) -> None:
        """Switch chat gen-type and switch to chat view."""
        self.state.generation_type = gtype
        self.state.current_view = "chat"
        self.app.show_chat_view()
        self.app.chat_view._set_gen_type(gtype)
        self.page.update()

    def _snack(self, message: str) -> None:
        self._cur_snackbar = ft.SnackBar(
            content=ft.Text(message, color=T.TEXT_PRIMARY),
            bgcolor=T.BG_CARD,
        )
        self.page.overlay.append(self._cur_snackbar)
        self._cur_snackbar.open = True
        self.page.update()

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Rebuild tools and cost bar (e.g. after project switch or cost update)."""
        if not self._container or getattr(self, "_collapsed", False):
            return
        try:
            self._tools_area.content = self._build_tools_section()
            self._tools_area.update()
            col = self._container.content
            col.controls[-1] = self._build_cost_bar()
            self._container.update()
        except Exception:
            pass
