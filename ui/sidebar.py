"""Left sidebar: project list, navigation."""
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.models import Project
from storage import project_repo, chat_repo

if TYPE_CHECKING:
    from ui.layout import AppLayout


class Sidebar:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state = app.state

        self._project_list_col: ft.Column = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)
        self._container: ft.Container | None = None

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Container:
        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    self._logo_area(),
                    T.divider(),
                    self._projects_header(),
                    self._project_list_col,
                    ft.Container(expand=True),  # spacer
                    T.divider(),
                    self._bottom_nav(),
                ],
                spacing=0,
                expand=True,
            ),
            width=T.SIDEBAR_WIDTH,
            bgcolor=T.BG_SIDEBAR,
            padding=ft.padding.only(bottom=8),
        )
        self._rebuild_project_list()
        return self._container

    # ── Sections ───────────────────────────────────────────────────────────────

    def _logo_area(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text("✦", size=20, color=T.ACCENT_LIGHT),
                        width=32,
                        height=32,
                        bgcolor=T.ACCENT_DIM,
                        border_radius=8,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("AI Ads Studio", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text("Content Generation", size=10, color=T.TEXT_MUTED),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=14),
        )

    def _projects_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "PROJECTS",
                        size=10,
                        weight=ft.FontWeight.W_700,
                        color=T.TEXT_MUTED,
            style=ft.TextStyle(letter_spacing=1.2),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="New Project",
                        on_click=self._open_create_project_dialog,
                        icon_color=T.TEXT_SECONDARY,
                        icon_size=16,
                        style=ft.ButtonStyle(
                            overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                            padding=ft.padding.symmetric(horizontal=4, vertical=4),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=12, right=4, top=12, bottom=4),
        )

    def _bottom_nav(self) -> ft.Column:
        items = [
            (ft.Icons.ROCKET_LAUNCH_OUTLINED, "Campaigns", "campaigns"),
            (ft.Icons.PALETTE_OUTLINED, "Brand", "brand"),
            (ft.Icons.CAMPAIGN_OUTLINED, "Brief", "brief"),
            (ft.Icons.PHOTO_LIBRARY_OUTLINED, "Assets", "assets"),
            (ft.Icons.SETTINGS_OUTLINED, "Settings", "settings"),
        ]
        buttons = []
        for icon, label, view in items:
            is_active = self.state.current_view == view
            buttons.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=16, color=T.ACCENT_LIGHT if is_active else T.TEXT_SECONDARY),
                            ft.Text(label, size=13, color=T.TEXT_PRIMARY if is_active else T.TEXT_SECONDARY),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=9),
                    border_radius=8,
                    bgcolor=T.ACCENT_DIM if is_active else ft.Colors.TRANSPARENT,
                    margin=ft.margin.symmetric(horizontal=6),
                    on_click=lambda e, v=view: self._navigate(v),
                    ink=True,
                )
            )
        return ft.Column(controls=buttons, spacing=2)

    # ── Project list ───────────────────────────────────────────────────────────

    def _rebuild_project_list(self) -> None:
        self._project_list_col.controls.clear()
        for project in self.state.projects:
            self._project_list_col.controls.append(
                self._project_item(project)
            )
        try:
            self._project_list_col.update()
        except Exception:
            pass

    def _project_item(self, project: Project) -> ft.Container:
        is_selected = (
            self.state.current_project is not None
            and self.state.current_project.id == project.id
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            project.name[0].upper(),
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=T.ACCENT_LIGHT,
                        ),
                        width=26,
                        height=26,
                        bgcolor=T.ACCENT_DIM,
                        border_radius=6,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(
                        project.name,
                        size=13,
                        color=T.TEXT_PRIMARY if is_selected else T.TEXT_SECONDARY,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_HORIZ,
                        icon_color=T.TEXT_MUTED,
                        icon_size=14,
                        tooltip="",
                        items=[
                            ft.PopupMenuItem(
                                text="Rename",
                                icon=ft.Icons.EDIT_OUTLINED,
                                on_click=lambda e, p=project: self._rename_project(p),
                            ),
                            ft.PopupMenuItem(
                                text="New Chat",
                                icon=ft.Icons.ADD_COMMENT_OUTLINED,
                                on_click=lambda e, p=project: self._new_chat(p),
                            ),
                            ft.PopupMenuItem(),  # divider
                            ft.PopupMenuItem(
                                text="Delete",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, p=project: self._delete_project(p),
                            ),
                        ],
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=7),
            border_radius=8,
            bgcolor=T.ACCENT_DIM if is_selected else ft.Colors.TRANSPARENT,
            margin=ft.margin.symmetric(horizontal=6),
            on_click=lambda e, p=project: self._select_project(p),
            ink=True,
        )

    # ── Actions ────────────────────────────────────────────────────────────────

    def _select_project(self, project: Project) -> None:
        self.state.select_project(project)
        self.state.current_view = "chat"
        self.refresh()
        self.app.show_chat_view()

    def _navigate(self, view: str) -> None:
        self.state.current_view = view
        self.refresh()
        if view == "campaigns":
            self.app.show_campaigns_view()
        elif view == "assets":
            self.app.show_assets_view()
        elif view == "settings":
            self.app.show_settings_view()
        elif view == "brief":
            self.app.show_brief_view()
        elif view == "brand":
            self.app.show_brand_view()
        elif view == "chat":
            self.app.show_chat_view()

    def _new_chat(self, project: Project) -> None:
        self.state.select_project(project)
        chat = chat_repo.create_chat(project_id=project.id)
        self.state.chats.insert(0, chat)
        self.state.current_chat = chat
        self.state.current_view = "chat"
        self.refresh()
        self.app.show_chat_view()

    def _open_create_project_dialog(self, e) -> None:
        name_field = T.styled_textfield("Project Name", hint="e.g. My Shopify Store")
        desc_field = T.styled_textfield("Description (optional)", hint="What does this brand sell?", multiline=True, min_lines=2, max_lines=3)

        def confirm(e):
            name = name_field.value.strip()
            if not name:
                name_field.error_text = "Name is required"
                name_field.update()
                return
            project = project_repo.create_project(name=name, description=desc_field.value.strip())
            self.state.refresh_projects()
            self.state.select_project(project)
            self.state.current_view = "chat"
            self._cur_dialog.open = False
            self.page.update()
            self.refresh()
            self.app.trigger_new_project_setup()

        def cancel(e):
            self._cur_dialog.open = False
            self.page.update()

        self._cur_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("New Project", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[name_field, desc_field],
                spacing=12,
                tight=True,
                width=380,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Create Project", on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(self._cur_dialog)
        self._cur_dialog.open = True
        self.page.update()

    def _rename_project(self, project: Project) -> None:
        name_field = T.styled_textfield("Project Name", value=project.name)

        def confirm(e):
            new_name = name_field.value.strip()
            if not new_name:
                return
            project.name = new_name
            project_repo.update_project(project)
            self.state.refresh_projects()
            self._cur_dialog.open = False
            self.page.update()
            self.refresh()
            if self.state.current_project and self.state.current_project.id == project.id:
                self.app.refresh_right_panel()

        def cancel(e):
            self._cur_dialog.open = False
            self.page.update()

        self._cur_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rename Project", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(controls=[name_field], tight=True, width=360),
            actions=[
                ft.TextButton("Cancel", on_click=cancel, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Save", on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(self._cur_dialog)
        self._cur_dialog.open = True
        self.page.update()

    def _delete_project(self, project: Project) -> None:
        def confirm(e):
            project_repo.delete_project(project.id)
            if self.state.current_project and self.state.current_project.id == project.id:
                self.state.current_project = None
                self.state.current_chat = None
            self.state.refresh_projects()
            self._cur_dialog.open = False
            self.page.update()
            self.refresh()
            self.app.show_chat_view()

        def cancel(e):
            self._cur_dialog.open = False
            self.page.update()

        self._cur_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Project?", color=T.ERROR, size=16, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Text(
                f'"{project.name}" and all its chats and assets will be permanently deleted.',
                color=T.TEXT_SECONDARY,
                size=13,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                ft.ElevatedButton(
                    "Delete",
                    on_click=confirm,
                    style=ft.ButtonStyle(
                        bgcolor={"": T.ERROR, "hovered": "#cc0000"},
                        color="#ffffff",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(self._cur_dialog)
        self._cur_dialog.open = True
        self.page.update()

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Rebuild the project list and bottom nav in place."""
        self._rebuild_project_list()
        if self._container:
            # Rebuild bottom nav to reflect active view
            col = self._container.content
            col.controls[-1] = self._bottom_nav()
            self._container.update()
