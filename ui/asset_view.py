"""Asset library view — shows saved assets per project."""
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage import asset_repo
from storage.models import Asset
from core.app_state import AppState

if TYPE_CHECKING:
    from ui.layout import AppLayout

_ASSET_TYPES = [
    ("all",           "All",            ft.Icons.GRID_VIEW_OUTLINED),
    ("text",          "Ad Copy",        ft.Icons.TEXT_FIELDS),
    ("image",         "Generated Images", ft.Icons.AUTO_AWESOME),
    ("image_prompt",  "Image Prompts",  ft.Icons.IMAGE_OUTLINED),
    ("video_prompt",  "Video Prompts",  ft.Icons.MOVIE_OUTLINED),
    ("bulk",          "Bulk Sets",      ft.Icons.FORMAT_LIST_BULLETED),
]


class AssetView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state: AppState = app.state
        self._current_filter = "all"
        self._asset_grid: ft.Column | None = None
        self._save_picker: ft.FilePicker | None = None
        self._save_pending_path: str = ""

    def build(self) -> ft.Column:
        if self._save_picker in self.page.overlay:
            try:
                self.page.overlay.remove(self._save_picker)
            except Exception:
                pass
        self._save_picker = ft.FilePicker(on_result=self._on_save_result)
        self.page.overlay.append(self._save_picker)

        self._asset_grid = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        self._load_assets()
        return ft.Column(
            controls=[
                self._header(),
                self._filter_bar(),
                T.divider(),
                ft.Container(
                    content=self._asset_grid,
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PHOTO_LIBRARY_OUTLINED, size=18, color=T.ACCENT_LIGHT),
                    ft.Text("Asset Library", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.Text(
                        f"Project: {self.state.current_project.name}" if self.state.current_project else "All Projects",
                        size=12,
                        color=T.TEXT_MUTED,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            bgcolor=T.BG_SECONDARY,
        )

    def _filter_bar(self) -> ft.Container:
        buttons = []
        for atype, label, icon in _ASSET_TYPES:
            is_active = self._current_filter == atype
            buttons.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=13, color=T.ACCENT_LIGHT if is_active else T.TEXT_MUTED),
                            ft.Text(label, size=12, color=T.TEXT_PRIMARY if is_active else T.TEXT_MUTED),
                        ],
                        spacing=5,
                        tight=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=6,
                    bgcolor=T.ACCENT_DIM if is_active else T.BG_CARD,
                    border=ft.border.all(1, T.BORDER_ACCENT if is_active else T.BORDER),
                    on_click=lambda e, t=atype: self._set_filter(t),
                    ink=True,
                )
            )
        return ft.Container(
            content=ft.Row(controls=buttons, spacing=6, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=T.BG_SECONDARY,
        )

    def _load_assets(self) -> None:
        if not self._asset_grid:
            return
        self._asset_grid.controls.clear()
        if not self.state.current_project:
            self._asset_grid.controls.append(
                ft.Container(
                    content=ft.Text("Select a project to view assets.", color=T.TEXT_MUTED, size=13),
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=40,
                )
            )
            return

        filter_type = None if self._current_filter == "all" else self._current_filter
        assets = asset_repo.get_assets(self.state.current_project.id, filter_type)

        if not assets:
            self._asset_grid.controls.append(self._empty_state())
            return

        for asset in assets:
            self._asset_grid.controls.append(self._asset_card(asset))

    def _empty_state(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.BOOKMARK_BORDER, color=T.TEXT_MUTED, size=40),
                    ft.Text("No assets yet", size=16, color=T.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        "Generate content in Chat and click 'Save to Assets' on any AI response.",
                        size=12,
                        color=T.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.alignment.center,
            expand=True,
            padding=40,
        )

    def _asset_card(self, asset: Asset) -> ft.Container:
        if asset.type == "image":
            return self._image_asset_card(asset)
        return self._text_asset_card(asset)

    def _image_asset_card(self, asset: Asset) -> ft.Container:
        path = asset.content  # content stores the file path for image assets
        actions = ft.Row(
            controls=[
                T.icon_button(
                    ft.Icons.DOWNLOAD_OUTLINED,
                    "Download image",
                    on_click=lambda e, p=path: self._download_image(p),
                    size=15,
                ),
                T.icon_button(
                    ft.Icons.CONTENT_COPY_OUTLINED,
                    "Copy image to clipboard",
                    on_click=lambda e, p=path: self._copy_image(p),
                    size=15,
                ),
                T.icon_button(
                    ft.Icons.FOLDER_OPEN_OUTLINED,
                    "Open folder",
                    on_click=lambda e, p=path: self._open_folder(p),
                    size=15,
                ),
                T.icon_button(
                    ft.Icons.DELETE_OUTLINE,
                    "Delete",
                    on_click=lambda e, a=asset: self._delete_asset(a),
                    size=15,
                    color=T.ERROR,
                ),
            ],
            spacing=0,
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Image(
                            src=path,
                            width=100,
                            height=100,
                            fit=ft.ImageFit.COVER,
                            border_radius=8,
                            error_content=ft.Container(
                                content=ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, size=24, color=T.TEXT_MUTED),
                                width=100, height=100, alignment=ft.alignment.center,
                            ),
                        ),
                        width=100,
                        height=100,
                        border_radius=8,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        border=ft.border.all(1, T.BORDER),
                    ),
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.AUTO_AWESOME, size=12, color=T.ACCENT_LIGHT),
                                        width=22, height=22, bgcolor=T.ACCENT_DIM,
                                        border_radius=5, alignment=ft.alignment.center,
                                    ),
                                    ft.Text(
                                        asset.title or "Generated Image",
                                        size=13, color=T.TEXT_PRIMARY,
                                        weight=ft.FontWeight.W_500,
                                        expand=True, overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    actions,
                                ],
                                spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                path, size=10, color=T.TEXT_MUTED,
                                overflow=ft.TextOverflow.ELLIPSIS, selectable=True,
                            ),
                            ft.Row(
                                controls=[
                                    T.provider_badge("local"),
                                    ft.Text(
                                        asset.created_at[:10] if asset.created_at else "",
                                        size=10, color=T.TEXT_MUTED,
                                    ),
                                ],
                                spacing=8,
                            ),
                        ],
                        spacing=4, expand=True, tight=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            bgcolor=T.BG_CARD,
            border_radius=10,
            border=ft.border.all(1, T.BORDER),
        )

    def _text_asset_card(self, asset: Asset) -> ft.Container:
        type_icons = {
            "text": ft.Icons.TEXT_FIELDS,
            "image_prompt": ft.Icons.IMAGE_OUTLINED,
            "video_prompt": ft.Icons.MOVIE_OUTLINED,
            "bulk": ft.Icons.FORMAT_LIST_BULLETED,
        }
        icon = type_icons.get(asset.type, ft.Icons.ARTICLE_OUTLINED)
        preview = asset.content[:200] + ("…" if len(asset.content) > 200 else "")

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon, size=14, color=T.ACCENT_LIGHT),
                                width=28, height=28, bgcolor=T.ACCENT_DIM,
                                border_radius=6, alignment=ft.alignment.center,
                            ),
                            ft.Text(
                                asset.title or asset.type.replace("_", " ").title(),
                                size=13, color=T.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500,
                                expand=True, overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Row(
                                controls=[
                                    T.icon_button(
                                        ft.Icons.CONTENT_COPY_OUTLINED,
                                        "Copy",
                                        on_click=lambda e, c=asset.content: self._copy(c),
                                        size=15,
                                    ),
                                    T.icon_button(
                                        ft.Icons.DELETE_OUTLINE,
                                        "Delete",
                                        on_click=lambda e, a=asset: self._delete_asset(a),
                                        size=15,
                                        color=T.ERROR,
                                    ),
                                ],
                                spacing=0,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    ft.Text(preview, size=12, color=T.TEXT_SECONDARY, selectable=True),
                    ft.Row(
                        controls=[
                            T.provider_badge(asset.provider) if asset.provider else ft.Container(),
                            ft.Text(asset.created_at[:10] if asset.created_at else "", size=10, color=T.TEXT_MUTED),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=14),
            bgcolor=T.BG_CARD,
            border_radius=10,
            border=ft.border.all(1, T.BORDER),
        )

    def _set_filter(self, atype: str) -> None:
        self._current_filter = atype
        self._load_assets()
        if self._asset_grid:
            try:
                self._asset_grid.update()
            except Exception:
                pass

    def _open_folder(self, file_path: str) -> None:
        import subprocess
        import sys
        from pathlib import Path
        folder = str(Path(file_path).parent)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", folder])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _download_image(self, path: str) -> None:
        import os
        self._save_pending_path = path
        if self._save_picker:
            self._save_picker.save_file(
                dialog_title="Save Image",
                file_name=os.path.basename(path),
                allowed_extensions=["png", "jpg", "jpeg", "webp"],
            )

    def _on_save_result(self, e) -> None:
        dest = getattr(e, "path", None)
        if not dest or not self._save_pending_path:
            return
        import shutil
        try:
            shutil.copy2(self._save_pending_path, dest)
            self._snack("Image saved ✓")
        except Exception as exc:
            self._snack(f"Could not save: {exc}", error=True)

    def _copy_image(self, path: str) -> None:
        import subprocess, sys
        try:
            if sys.platform == "win32":
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "Add-Type -AssemblyName System.Drawing; "
                    f"$img = [System.Drawing.Image]::FromFile('{path}'); "
                    "[System.Windows.Forms.Clipboard]::SetImage($img); "
                    "$img.Dispose()"
                )
                subprocess.run(["powershell", "-Command", ps], timeout=10, check=True)
            elif sys.platform == "darwin":
                subprocess.run(
                    ["osascript", "-e", f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'],
                    timeout=10, check=True,
                )
            else:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", path],
                    timeout=10, check=True,
                )
            self._snack("Image copied to clipboard ✓")
        except FileNotFoundError:
            self.page.set_clipboard(path)
            self._snack("Copied image path (install xclip for full image copy on Linux)")
        except Exception:
            self.page.set_clipboard(path)
            self._snack("Copied image path to clipboard")

    def _snack(self, message: str, error: bool = False) -> None:
        from ui import theme as _T
        bar = ft.SnackBar(
            content=ft.Text(message, color=_T.TEXT_PRIMARY),
            bgcolor=_T.ERROR if error else _T.BG_CARD,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()

    def _copy(self, content: str) -> None:
        self.page.set_clipboard(content)
        self._cur_snackbar = ft.SnackBar(
            content=ft.Text("Copied to clipboard", color=T.TEXT_PRIMARY),
            bgcolor=T.BG_CARD,
        )
        self.page.overlay.append(self._cur_snackbar)
        self._cur_snackbar.open = True
        self.page.update()

    def _delete_asset(self, asset: Asset) -> None:
        def confirm(e):
            asset_repo.delete_asset(asset.id)
            self._cur_dialog.open = False
            self._set_filter(self._current_filter)
            self.page.update()

        def cancel(e):
            self._cur_dialog.open = False
            self.page.update()

        self._cur_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Asset?", color=T.ERROR, size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Text("This action cannot be undone.", color=T.TEXT_SECONDARY, size=13),
            actions=[
                ft.TextButton("Cancel", on_click=cancel, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                ft.ElevatedButton(
                    "Delete",
                    on_click=confirm,
                    style=ft.ButtonStyle(
                        bgcolor={"": T.ERROR},
                        color="#ffffff",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.append(self._cur_dialog)
        self._cur_dialog.open = True
        self.page.update()
