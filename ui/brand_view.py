"""Brand identity editor — full main-area view."""
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.project_repo import update_project

if TYPE_CHECKING:
    from ui.layout import AppLayout


class BrandView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state = app.state

    def build(self) -> ft.Container:
        project = self.state.current_project
        if not project:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=T.TEXT_MUTED, size=40),
                        ft.Text("No project selected", color=T.TEXT_MUTED, size=14, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "Create or select a project from the sidebar first.",
                            color=T.TEXT_MUTED,
                            size=12,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                expand=True,
                alignment=ft.alignment.center,
                bgcolor=T.BG_PRIMARY,
            )

        fields_def = [
            ("Slogan", "slogan", project.slogan, False),
            ("Description", "description", project.description, True),
            ("Brand Colors", "brand_colors", project.brand_colors, False),
            ("Fonts", "fonts", project.fonts, False),
            ("Legal Info", "legal_info", project.legal_info, True),
        ]
        field_refs: dict[str, ft.TextField] = {}
        field_controls = []

        for label, attr, value, multiline in fields_def:
            tf = ft.TextField(
                label=label,
                value=value,
                multiline=multiline,
                min_lines=2 if multiline else 1,
                max_lines=5 if multiline else 1,
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                label_style=ft.TextStyle(color=T.TEXT_MUTED),
                cursor_color=T.ACCENT_LIGHT,
                border_radius=8,
                text_size=13,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            )
            field_refs[attr] = tf
            field_controls.append(tf)

        def save_brand(e):
            for attr, tf in field_refs.items():
                setattr(project, attr, tf.value or "")
            update_project(project)
            self.state.refresh_projects()
            snack = ft.SnackBar(
                content=ft.Text("Brand saved", color=T.TEXT_PRIMARY),
                bgcolor=T.BG_CARD,
            )
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            project.name[0].upper(),
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=T.ACCENT_LIGHT,
                        ),
                        width=44,
                        height=44,
                        bgcolor=T.ACCENT_DIM,
                        border_radius=10,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(project.name, size=18, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text("Brand Identity", size=12, color=T.TEXT_MUTED),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=0, bottom=20),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                header,
                                *field_controls,
                                ft.Container(height=8),
                                T.accent_button("Save Brand", on_click=save_brand, width=360),
                            ],
                            spacing=12,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        padding=ft.padding.symmetric(horizontal=40, vertical=32),
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
            bgcolor=T.BG_PRIMARY,
        )
