"""Settings view — API keys and application preferences."""
import threading
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.asset_repo import save_api_key, get_all_api_keys
from ai_providers.router import list_providers
from ai_providers.local_model_catalog import CATALOG
from ai_providers.ollama_provider import (
    is_ollama_running,
    is_ollama_installed,
    list_installed_models,
    pull_model,
    delete_model,
    install_ollama,
    start_ollama,
)

if TYPE_CHECKING:
    from ui.layout import AppLayout

_PROVIDER_INFO = {
    "openai": {
        "label": "OpenAI",
        "desc": "GPT-4o, GPT-4o-mini, o1 and more",
        "url": "https://platform.openai.com/api-keys",
        "icon": "🟢",
    },
    "claude": {
        "label": "Anthropic Claude",
        "desc": "Claude 3.5 Sonnet, Haiku, Opus",
        "url": "https://console.anthropic.com/settings/keys",
        "icon": "🟠",
    },
    "gemini": {
        "label": "Google Gemini",
        "desc": "Gemini 2.0 Flash, 1.5 Pro",
        "url": "https://aistudio.google.com/apikey",
        "icon": "🔵",
    },
}


class SettingsView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app

    def build(self) -> ft.Column:
        existing_keys = get_all_api_keys()
        provider_cards = []
        key_fields: dict[str, ft.TextField] = {}

        for provider in list_providers():
            info = _PROVIDER_INFO.get(provider, {"label": provider, "desc": "", "url": "", "icon": "•"})
            existing = existing_keys.get(provider, "")
            # Mask existing key for display
            display_value = ("•" * 8 + existing[-4:]) if len(existing) > 8 else existing

            tf = ft.TextField(
                label=f"{info['label']} API Key",
                value=display_value,
                password=True,
                can_reveal_password=True,
                hint_text="sk-..." if provider == "openai" else "Enter API key",
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                label_style=ft.TextStyle(color=T.TEXT_MUTED),
                hint_style=ft.TextStyle(color=T.TEXT_MUTED),
                cursor_color=T.ACCENT_LIGHT,
                border_radius=8,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
                expand=True,
            )
            key_fields[provider] = tf

            is_configured = bool(existing.strip())
            provider_cards.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(info["icon"], size=20),
                                    ft.Column(
                                        controls=[
                                            ft.Text(info["label"], size=14, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                                            ft.Text(info["desc"], size=11, color=T.TEXT_MUTED),
                                        ],
                                        spacing=1,
                                        tight=True,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            "✓ Configured" if is_configured else "Not set",
                                            size=11,
                                            color=T.SUCCESS if is_configured else T.TEXT_MUTED,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        bgcolor="#052e16" if is_configured else T.BG_SECONDARY,
                                        border_radius=6,
                                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                        border=ft.border.all(1, T.SUCCESS if is_configured else T.BORDER),
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Row(
                                controls=[
                                    tf,
                                    ft.TextButton(
                                        "Get Key",
                                        url=info["url"],
                                        style=ft.ButtonStyle(color=T.TEXT_ACCENT),
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=12,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    bgcolor=T.BG_CARD,
                    border_radius=10,
                    border=ft.border.all(1, T.SUCCESS if is_configured else T.BORDER),
                )
            )

        def save_keys(e):
            saved_any = False
            for provider, tf in key_fields.items():
                val = tf.value.strip()
                # Skip if it looks like a masked existing key (all dots)
                if val and not all(c in "•" for c in val):
                    save_api_key(provider, val)
                    saved_any = True
            if saved_any:
                self._snack("API keys saved ✓")
                self.app.show_settings_view()  # Rebuild to show updated statuses
            else:
                self._snack("No changes to save")

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=18, color=T.ACCENT_LIGHT),
                            ft.Text("Settings", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    bgcolor=T.BG_SECONDARY,
                ),
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("AI Provider API Keys", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(
                                "API keys are stored locally on your machine and never shared.",
                                size=12,
                                color=T.TEXT_MUTED,
                            ),
                            ft.Container(height=8),
                            *provider_cards,
                            ft.Container(height=16),
                            T.accent_button("Save API Keys", on_click=save_keys, icon=ft.Icons.SAVE_OUTLINED),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            self._build_local_models_section(),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            ft.Text("Storage", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FOLDER_OUTLINED, size=16, color=T.TEXT_MUTED),
                                        ft.Text(
                                            str(self._db_path()),
                                            size=12,
                                            color=T.TEXT_SECONDARY,
                                            selectable=True,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                bgcolor=T.BG_CARD,
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=12, vertical=12),
                                border=ft.border.all(1, T.BORDER),
                            ),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            ft.Text("About", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(
                                "AI Ads & Content Generation Studio\nVersion 1.0.0 MVP\nBuilt with Flet + Python",
                                size=12,
                                color=T.TEXT_MUTED,
                            ),
                        ],
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=24, vertical=16),
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _build_local_models_section(self) -> ft.Column:
        """Build the Local Models (Ollama) settings section."""
        running = is_ollama_running()
        installed = {m["name"].split(":")[0] + ":" + m["name"].split(":")[-1]
                     if ":" in m["name"] else m["name"] + ":latest"
                     for m in list_installed_models()}
        # Normalise: strip ":latest" suffix for comparison
        installed_norm = {n.replace(":latest", "") for n in installed} | installed

        status_color = T.SUCCESS if running else T.ERROR
        status_bg = "#052e16" if running else "#2d0a0a"

        model_rows: list[ft.Control] = []
        for entry in CATALOG:
            mid = entry["id"]
            is_installed = mid in installed_norm or mid.split(":")[0] in installed_norm

            btn_ref = ft.Ref[ft.ElevatedButton]()
            status_ref = ft.Ref[ft.Text]()

            def make_pull(model_id=mid, btn=btn_ref, stat=status_ref):
                def do_pull(e):
                    btn.current.disabled = True
                    btn.current.text = "Downloading…"
                    stat.current.value = "Starting…"
                    self.page.update()

                    def run():
                        def on_prog(msg):
                            stat.current.value = msg
                            try:
                                self.page.update()
                            except Exception:
                                pass

                        ok = pull_model(model_id, on_progress=on_prog)
                        if ok:
                            stat.current.value = "Installed ✓"
                            btn.current.text = "Installed"
                        else:
                            stat.current.value = "Download failed"
                            btn.current.disabled = False
                            btn.current.text = "Download"
                        try:
                            self.page.update()
                        except Exception:
                            pass

                    threading.Thread(target=run, daemon=True).start()
                return do_pull

            def make_delete(model_id=mid, btn=btn_ref, stat=status_ref):
                def do_delete(e):
                    stat.current.value = "Deleting…"
                    self.page.update()
                    ok = delete_model(model_id)
                    stat.current.value = "Deleted" if ok else "Delete failed"
                    btn.current.text = "Download"
                    btn.current.disabled = not running
                    self.page.update()
                return do_delete

            initial_status = "Installed ✓" if is_installed else ""
            action_btn = ft.ElevatedButton(
                ref=btn_ref,
                text="Installed" if is_installed else "Download",
                disabled=is_installed or not running,
                on_click=make_pull() if not is_installed else make_delete(),
                style=ft.ButtonStyle(
                    bgcolor={
                        "": T.SUCCESS if is_installed else (T.ACCENT if running else T.BG_SECONDARY),
                        "disabled": T.BG_SECONDARY,
                    },
                    color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                ),
            )

            tags_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(tag, size=10, color=T.ACCENT_LIGHT),
                        bgcolor=T.BG_SECONDARY,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border=ft.border.all(1, T.BORDER),
                    )
                    for tag in entry.get("tags", [])
                ],
                spacing=4,
                wrap=True,
            )

            model_rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(entry["label"], size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                                            ft.Text(f"{entry['size_gb']} GB", size=11, color=T.TEXT_MUTED),
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(entry["description"], size=11, color=T.TEXT_SECONDARY),
                                    tags_row,
                                    ft.Text(ref=status_ref, value=initial_status, size=11, color=T.SUCCESS, italic=True),
                                ],
                                spacing=3,
                                expand=True,
                                tight=True,
                            ),
                            action_btn,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=T.BG_CARD,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=14, vertical=12),
                    border=ft.border.all(1, T.SUCCESS if is_installed else T.BORDER),
                )
            )

        # ── Ollama status bar with Install / Start buttons ─────────────────
        installed_app = is_ollama_installed()
        ollama_status_ref = ft.Ref[ft.Text]()
        ollama_badge_ref = ft.Ref[ft.Container]()
        install_btn_ref = ft.Ref[ft.ElevatedButton]()
        start_btn_ref = ft.Ref[ft.ElevatedButton]()
        hint_ref = ft.Ref[ft.Container]()

        def _refresh_ollama_state(is_running: bool):
            """Rebuild the settings view to reflect updated Ollama state."""
            try:
                self.app.show_settings_view()
            except Exception:
                pass

        def on_install(e):
            install_btn_ref.current.disabled = True
            install_btn_ref.current.text = "Installing…"
            ollama_status_ref.current.value = "Downloading installer…"
            self.page.update()

            def run():
                def on_status(msg):
                    ollama_status_ref.current.value = msg
                    try:
                        self.page.update()
                    except Exception:
                        pass

                ok = install_ollama(on_status=on_status)
                now_running = is_ollama_running()
                if not ok:
                    on_status("Install failed — try manually at ollama.com/download")
                _refresh_ollama_state(now_running)

            threading.Thread(target=run, daemon=True).start()

        def on_start(e):
            start_btn_ref.current.disabled = True
            start_btn_ref.current.text = "Starting…"
            ollama_status_ref.current.value = "Starting Ollama…"
            self.page.update()

            def run():
                start_ollama()
                _refresh_ollama_state(is_ollama_running())

            threading.Thread(target=run, daemon=True).start()

        initial_status_text = (
            "Running ✓" if running else
            ("Stopped" if installed_app else "Not installed")
        )

        ollama_action_row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    ref=install_btn_ref,
                    text="Install Ollama",
                    icon=ft.Icons.DOWNLOAD_OUTLINED,
                    visible=not installed_app,
                    on_click=on_install,
                    style=ft.ButtonStyle(
                        bgcolor={"": T.ACCENT, "disabled": T.BG_SECONDARY},
                        color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                        shape=ft.RoundedRectangleBorder(radius=7),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                ),
                ft.ElevatedButton(
                    ref=start_btn_ref,
                    text="Start Ollama",
                    icon=ft.Icons.PLAY_ARROW_OUTLINED,
                    visible=installed_app and not running,
                    on_click=on_start,
                    style=ft.ButtonStyle(
                        bgcolor={"": T.SUCCESS, "disabled": T.BG_SECONDARY},
                        color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                        shape=ft.RoundedRectangleBorder(radius=7),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                ),
            ],
            spacing=8,
        )

        hint_box = ft.Container(
            ref=hint_ref,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=T.ACCENT_LIGHT),
                            ft.Text("Ollama is not running", size=12, color=T.TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        "Install and start Ollama above to enable local model downloads.\n"
                        "Models run fully offline — no API key, no cost.",
                        size=11,
                        color=T.TEXT_MUTED,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=T.BG_SECONDARY,
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            border=ft.border.all(1, T.BORDER),
            visible=not running,
        )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPUTER_OUTLINED, size=16, color=T.ACCENT_LIGHT),
                        ft.Text("Local Models", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Text(
                                ref=ollama_status_ref,
                                value=initial_status_text,
                                size=11,
                                color=status_color,
                                weight=ft.FontWeight.W_600,
                            ),
                            ref=ollama_badge_ref,
                            bgcolor=status_bg,
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border=ft.border.all(1, status_color),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Run AI models locally — no API key, no cost. Download once, use offline forever.",
                    size=12,
                    color=T.TEXT_MUTED,
                ),
                ollama_action_row,
                hint_box,
                ft.Container(height=4),
                *model_rows,
            ],
            spacing=8,
            tight=True,
        )

    def _db_path(self):
        from storage.db import get_db_path
        return get_db_path()

    def _snack(self, message: str) -> None:
        self._cur_snackbar = ft.SnackBar(
            content=ft.Text(message, color=T.TEXT_PRIMARY),
            bgcolor=T.BG_CARD,
        )
        self.page.overlay.append(self._cur_snackbar)
        self._cur_snackbar.open = True
        self.page.update()

