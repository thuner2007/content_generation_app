"""Right panel: brand context, cost monitor, and quick tools."""
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage import asset_repo
from storage.project_repo import update_project
from core.app_state import AppState
from services.cost_estimator import estimate

if TYPE_CHECKING:
    from ui.layout import AppLayout


class RightPanel:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state: AppState = app.state

        self._tabs: ft.Tabs | None = None
        self._brand_tab_content: ft.Column | None = None
        self._cost_tab_content: ft.Column | None = None
        self._container: ft.Container | None = None

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Container:
        self._tabs = ft.Tabs(
            selected_index=0,
            animation_duration=150,
            tab_alignment=ft.TabAlignment.FILL,
            tabs=[
                ft.Tab(text="Brand", icon=ft.Icons.PALETTE_OUTLINED),
                ft.Tab(text="Cost", icon=ft.Icons.ATTACH_MONEY),
                ft.Tab(text="Tools", icon=ft.Icons.BOLT_OUTLINED),
            ],
            on_change=self._on_tab_change,
            expand=True,
            label_color=T.TEXT_PRIMARY,
            unselected_label_color=T.TEXT_MUTED,
            indicator_color=T.ACCENT,
            indicator_tab_size=True,
            overlay_color=ft.Colors.TRANSPARENT,
        )

        self._tab_content = ft.Container(expand=True, content=self._build_brand_tab())

        self._container = ft.Container(
            content=ft.Column(
                controls=[self._tabs, self._tab_content],
                spacing=0,
                expand=True,
            ),
            width=T.PANEL_WIDTH,
            bgcolor=T.BG_SIDEBAR,
            padding=0,
        )
        return self._container

    # ── Tab content builders ───────────────────────────────────────────────────

    def _build_brand_tab(self) -> ft.Column:
        project = self.state.current_project
        if not project:
            return ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=T.TEXT_MUTED, size=32),
                                ft.Text("No project selected", color=T.TEXT_MUTED, size=13, text_align=ft.TextAlign.CENTER),
                                ft.Text(
                                    "Create or select a project from the sidebar to see brand context.",
                                    color=T.TEXT_MUTED,
                                    size=12,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        expand=True,
                        alignment=ft.alignment.center,
                        padding=24,
                    )
                ],
                expand=True,
            )

        # Editable brand fields
        fields = [
            ("Slogan", "slogan", project.slogan, False),
            ("Description", "description", project.description, True),
            ("Brand Colors", "brand_colors", project.brand_colors, False),
            ("Fonts", "fonts", project.fonts, False),
            ("Legal Info", "legal_info", project.legal_info, True),
        ]
        field_controls = []
        field_refs: dict[str, ft.TextField] = {}
        for label, attr, value, multiline in fields:
            tf = ft.TextField(
                label=label,
                value=value,
                multiline=multiline,
                min_lines=1,
                max_lines=3 if multiline else 1,
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                label_style=ft.TextStyle(color=T.TEXT_MUTED),
                cursor_color=T.ACCENT_LIGHT,
                border_radius=8,
                text_size=12,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
            )
            field_refs[attr] = tf
            field_controls.append(tf)

        def save_brand(e):
            for attr, tf in field_refs.items():
                setattr(project, attr, tf.value or "")
            update_project(project)
            self.state.refresh_projects()
            self._snack("Brand saved ✓")

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    project.name[0].upper(),
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=T.ACCENT_LIGHT,
                                ),
                                width=36,
                                height=36,
                                bgcolor=T.ACCENT_DIM,
                                border_radius=8,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(project.name, size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                    ft.Text("Brand Identity", size=11, color=T.TEXT_MUTED),
                                ],
                                spacing=1,
                                tight=True,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=14),
                ),
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            *field_controls,
                            ft.Container(height=4),
                            T.accent_button("Save Brand", on_click=save_brand, width=T.PANEL_WIDTH - 28),
                        ],
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        )

    def _build_cost_tab(self) -> ft.Column:
        summary = asset_repo.get_usage_summary()
        total = asset_repo.get_total_cost()
        project_cost = 0.0
        if self.state.current_project:
            project_cost = asset_repo.get_total_cost(self.state.current_project.id)

        rows = []
        for item in summary:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            T.provider_badge(item["provider"]),
                            ft.Container(expand=True),
                            ft.Column(
                                controls=[
                                    ft.Text(f"${item['total_cost']:.4f}", size=12, color=T.TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                                    ft.Text(f"{item['requests']} requests", size=10, color=T.TEXT_MUTED),
                                ],
                                spacing=1,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                tight=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    bgcolor=T.BG_CARD,
                    border_radius=8,
                    border=ft.border.all(1, T.BORDER),
                )
            )

        # Cost estimate for current input
        est = estimate(
            user_input="",
            provider_name=self.state.selected_provider,
            model=self.state.selected_model,
            history_length=0,
        )

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Usage Summary", size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                            ft.Container(height=4),
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=[
                                            ft.Text(f"${total:.4f}", size=20, weight=ft.FontWeight.BOLD, color=T.ACCENT_LIGHT),
                                            ft.Text("Total Spend", size=11, color=T.TEXT_MUTED),
                                        ],
                                        spacing=2,
                                    ),
                                    ft.Container(expand=True),
                                    ft.Column(
                                        controls=[
                                            ft.Text(f"${project_cost:.4f}", size=20, weight=ft.FontWeight.BOLD, color=T.SUCCESS),
                                            ft.Text("This Project", size=11, color=T.TEXT_MUTED),
                                        ],
                                        spacing=2,
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                    ),
                                ],
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=14),
                ),
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("By Provider", size=12, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600),
                            ft.Container(height=6),
                            *(rows if rows else [ft.Text("No usage yet", size=12, color=T.TEXT_MUTED)]),
                            ft.Container(height=12),
                            T.divider(),
                            ft.Container(height=8),
                            ft.Text("Next Generation Estimate", size=12, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600),
                            ft.Container(height=4),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Text(est["cost_display"], size=18, weight=ft.FontWeight.BOLD, color=T.WARNING),
                                        ft.Container(expand=True),
                                        ft.Text(f"~{est['tokens']} tokens", size=11, color=T.TEXT_MUTED),
                                    ],
                                ),
                                bgcolor=T.BG_CARD,
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=12, vertical=12),
                                border=ft.border.all(1, T.BORDER),
                            ),
                        ],
                        spacing=4,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        )

    def _build_tools_tab(self) -> ft.Column:
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
                    content=ft.Text("Quick Launch", size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                    padding=ft.padding.only(left=14, top=14, bottom=8),
                ),
                ft.Column(
                    controls=tool_cards,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_tab_change(self, e) -> None:
        idx = e.control.selected_index
        if idx == 0:
            self._tab_content.content = self._build_brand_tab()
        elif idx == 1:
            self._tab_content.content = self._build_cost_tab()
        elif idx == 2:
            self._tab_content.content = self._build_tools_tab()
        self._tab_content.update()

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
        """Rebuild current tab content (e.g. after project switch or cost update)."""
        if not self._tabs or not self._tab_content:
            return
        idx = self._tabs.selected_index
        if idx == 0:
            self._tab_content.content = self._build_brand_tab()
        elif idx == 1:
            self._tab_content.content = self._build_cost_tab()
        elif idx == 2:
            self._tab_content.content = self._build_tools_tab()
        try:
            self._tab_content.update()
        except Exception:
            pass
