"""Settings view — API keys and application preferences."""
import threading
import time as _time
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.asset_repo import save_api_key, get_all_api_keys
from ai_providers.router import list_providers
from ai_providers.local_model_catalog import CATALOG, CATEGORY_ORDER, _CATEGORY_META
from ai_providers.local_image_provider import IMAGE_MODEL_CATALOG, _TIER_LABELS, get_gpu_info
from ai_providers.cloud_media_catalog import (
    CLOUD_IMAGE_CATALOG, CLOUD_VIDEO_CATALOG, CLOUD_DEDICATED_KEYS,
    _CLOUD_CATEGORY_LABELS,
)
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

# Caches so the Settings view opens instantly; background threads refresh on stale data.
_OLLAMA_STATE: dict = {"ts": 0.0, "running": False, "installed": frozenset(), "checking": False}
_IMGBACKEND_STATE: dict = {"ts": 0.0, "a1111": False, "comfyui": False, "checking": False}
_IMGDEPS_STATE: dict = {"ts": 0.0, "deps": {}, "installed_ids": [], "gpu": {}, "checking": False}
_CACHE_TTL = 30.0  # seconds

# Debounce timer so multiple background threads collapse into a single settings rebuild.
_REBUILD_TIMER: dict = {"timer": None}


def _pkg_installed(import_name: str) -> bool:
    """Return True if the given dotted import name is importable."""
    import importlib.util
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


_PROVIDER_PACKAGES: dict[str, list[tuple[str, str]]] = {
    "openai":  [("openai",              "openai")],
    "claude":  [("anthropic",           "anthropic")],
    "gemini":  [
        ("google.generativeai", "google-generativeai"),
        ("google.genai",        "google-genai"),
    ],
}


def _debounced_rebuild(app: "AppLayout", view_state, delay: float = 0.5) -> None:
    """Schedule one settings rebuild; cancels any already-pending rebuild."""
    if _REBUILD_TIMER["timer"] is not None:
        _REBUILD_TIMER["timer"].cancel()

    def _do():
        if getattr(view_state, "current_view", None) == "settings":
            try:
                app.show_settings_view()
            except Exception:
                pass

    t = threading.Timer(delay, _do)
    _REBUILD_TIMER["timer"] = t
    t.start()

_PROVIDER_INFO = {
    "openai": {
        "label": "OpenAI",
        "desc": "GPT-4.1, o3, o4-mini, GPT-4o — also enables Sora video & GPT-Image-1",
        "url": "https://platform.openai.com/api-keys",
        "icon": "🟢",
    },
    "claude": {
        "label": "Anthropic Claude",
        "desc": "Claude Opus 4.7, Sonnet 4.6, Haiku 4.5",
        "url": "https://console.anthropic.com/settings/keys",
        "icon": "🟠",
    },
    "gemini": {
        "label": "Google Gemini",
        "desc": "Gemini 3.5 Flash, 2.5 Pro/Flash — also enables Nano Banana Pro images",
        "url": "https://aistudio.google.com/apikey",
        "icon": "🔵",
    },
}


class SettingsView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app

    def _make_install_btn(self, pkgs: list[str], label: str):
        """Return (button, status_text) that runs pip install <pkgs> on click."""
        btn_ref  = ft.Ref[ft.ElevatedButton]()
        stat_ref = ft.Ref[ft.Text]()

        def on_install(e):
            btn_ref.current.disabled = True
            btn_ref.current.text = "Installing…"
            stat_ref.current.value = "This may take a few minutes…"
            try:
                self.page.update()
            except Exception:
                pass

            def run():
                import subprocess, sys
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs,
                        capture_output=True, text=True, timeout=600,
                    )
                    if proc.returncode == 0:
                        stat_ref.current.value = f"{label} installed ✓"
                        _IMGDEPS_STATE["ts"] = 0.0
                        _debounced_rebuild(self.app, self.app.state, delay=0.5)
                    else:
                        err = (proc.stderr or proc.stdout or "unknown error").strip()[-200:]
                        stat_ref.current.value = f"Failed: {err}"
                        btn_ref.current.disabled = False
                        btn_ref.current.text = "Retry"
                except subprocess.TimeoutExpired:
                    stat_ref.current.value = "Timed out — try running pip manually"
                    btn_ref.current.disabled = False
                    btn_ref.current.text = "Retry"
                except Exception as exc:
                    stat_ref.current.value = f"Error: {exc}"
                    btn_ref.current.disabled = False
                    btn_ref.current.text = "Retry"
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Thread(target=run, daemon=True).start()

        btn = ft.ElevatedButton(
            ref=btn_ref,
            text=f"Install {label}",
            icon=ft.Icons.DOWNLOAD_OUTLINED,
            on_click=on_install,
            style=ft.ButtonStyle(
                bgcolor={"": T.ACCENT, "disabled": T.BG_SECONDARY},
                color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                shape=ft.RoundedRectangleBorder(radius=7),
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
            ),
        )
        stat = ft.Text(ref=stat_ref, value="", size=11, color=T.TEXT_MUTED, italic=True)
        return btn, stat

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

            # Package dependency row
            _pkg_entries = _PROVIDER_PACKAGES.get(provider, [])
            _missing = [(imp, pip) for imp, pip in _pkg_entries if not _pkg_installed(imp)]
            _pkg_controls: list[ft.Control] = []
            if _missing:
                _pip_names = [pip for _, pip in _missing]
                _disp_label = " + ".join(imp.split(".")[0] for imp, _ in _missing)
                _inst_btn, _inst_stat = self._make_install_btn(_pip_names, _disp_label)
                _pkg_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=13, color="#f59e0b"),
                                        ft.Text(
                                            f"Package{'s' if len(_pip_names) > 1 else ''} not installed: {', '.join(_pip_names)}",
                                            size=11, color="#f59e0b", expand=True,
                                        ),
                                    ],
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Row(
                                    controls=[_inst_btn, _inst_stat],
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        bgcolor="#451a03",
                        border_radius=6,
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                        border=ft.border.all(1, "#92400e"),
                    )
                )

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
                            *_pkg_controls,
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
                    # Invalidate the balance cache so the header re-fetches
                    try:
                        from ai_providers.balance_fetcher import invalidate
                        invalidate(provider)
                    except Exception:
                        pass
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
                            self._build_default_model_section(),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            self._build_local_models_section(),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            self._build_local_image_section(),
                            ft.Container(height=24),
                            T.divider(),
                            ft.Container(height=16),
                            self._build_cloud_media_section(),
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

    def _build_default_model_section(self) -> ft.Container:
        from storage.settings_repo import get_setting, set_setting
        from ai_providers.router import list_providers, get_models_for_provider

        cur_provider = get_setting("default_provider") or self.app.state.selected_provider
        cur_model = get_setting("default_model") or self.app.state.selected_model

        all_providers = list_providers()
        if cur_provider not in all_providers:
            cur_provider = all_providers[0] if all_providers else "openai"

        models = get_models_for_provider(cur_provider)
        if cur_model not in models:
            cur_model = models[0] if models else ""

        model_dd = ft.Dropdown(
            value=cur_model,
            options=[ft.dropdown.Option(m) for m in models],
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=8,
            expand=True,
        )

        saved_badge = ft.Text("", size=11, color=T.SUCCESS)

        def on_provider_change(e):
            new_provider = e.control.value
            new_models = get_models_for_provider(new_provider)
            model_dd.options = [ft.dropdown.Option(m) for m in new_models]
            new_model = new_models[0] if new_models else ""
            model_dd.value = new_model
            set_setting("default_provider", new_provider)
            set_setting("default_model", new_model)
            self.app.state.selected_provider = new_provider
            self.app.state.selected_model = new_model
            saved_badge.value = "Saved ✓"
            model_dd.update()
            saved_badge.update()

        def on_model_change(e):
            new_model = e.control.value or ""
            provider_dd.value  # current provider
            set_setting("default_provider", provider_dd.value)
            set_setting("default_model", new_model)
            self.app.state.selected_model = new_model
            saved_badge.value = "Saved ✓"
            saved_badge.update()

        model_dd.on_change = on_model_change

        provider_dd = ft.Dropdown(
            value=cur_provider,
            options=[ft.dropdown.Option(p, p.capitalize()) for p in all_providers],
            on_change=on_provider_change,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=8,
            width=130,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TUNE_OUTLINED, size=16, color=T.ACCENT_LIGHT),
                            ft.Text(
                                "Default Chat Model",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                                color=T.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            saved_badge,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Used automatically when you open a new chat. "
                        "Switching models in the chat header also updates this.",
                        size=12,
                        color=T.TEXT_MUTED,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[
                            ft.Text("Provider", size=12, color=T.TEXT_MUTED, width=56),
                            provider_dd,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Model", size=12, color=T.TEXT_MUTED, width=56),
                            model_dd,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=16),
            bgcolor=T.BG_CARD,
            border_radius=10,
            border=ft.border.all(1, T.BORDER),
        )

    def _build_local_models_section(self) -> ft.Column:
        """Build the Local Models (Ollama) settings section, grouped by category."""
        state = _OLLAMA_STATE
        now = _time.time()
        use_cache = state["ts"] > 0 and (now - state["ts"]) < _CACHE_TTL

        if not use_cache and not state["checking"]:
            state["checking"] = True

            def _bg_ollama(app=self.app, view_state=self.app.state):
                r = is_ollama_running()
                raw = {
                    (m["name"].split(":")[0] + ":" + m["name"].split(":")[-1]
                     if ":" in m["name"] else m["name"] + ":latest")
                    for m in (list_installed_models() if r else [])
                }
                _OLLAMA_STATE["running"] = r
                _OLLAMA_STATE["installed"] = frozenset(
                    {n.replace(":latest", "") for n in raw} | raw
                )
                _OLLAMA_STATE["ts"] = _time.time()
                _OLLAMA_STATE["checking"] = False
                _debounced_rebuild(app, view_state)

            threading.Thread(target=_bg_ollama, daemon=True).start()

        running = state["running"]
        installed_norm = set(state["installed"])

        status_color = T.SUCCESS if running else T.ERROR
        status_bg    = "#052e16" if running else "#2d0a0a"

        def _is_installed(mid: str) -> bool:
            return mid in installed_norm or mid.split(":")[0] in installed_norm

        def _make_model_card(entry: dict) -> ft.Container:
            mid        = entry["id"]
            installed  = _is_installed(mid)
            is_vision  = entry.get("vision", False)
            btn_ref    = ft.Ref[ft.ElevatedButton]()
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
                            try: self.page.update()
                            except Exception: pass
                        ok = pull_model(model_id, on_progress=on_prog)
                        if ok:
                            stat.current.value = "Installed ✓"
                            btn.current.text = "Installed"
                        else:
                            stat.current.value = "Download failed"
                            btn.current.disabled = False
                            btn.current.text = "Download"
                        try: self.page.update()
                        except Exception: pass
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

            action_btn = ft.ElevatedButton(
                ref=btn_ref,
                text="Installed" if installed else "Download",
                disabled=installed or not running,
                on_click=make_pull() if not installed else make_delete(),
                style=ft.ButtonStyle(
                    bgcolor={
                        "": T.SUCCESS if installed else (T.ACCENT if running else T.BG_SECONDARY),
                        "disabled": T.BG_SECONDARY,
                    },
                    color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                ),
            )

            # Vision badge shown on the label row
            vision_badge = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=10, color=T.ACCENT_LIGHT),
                        ft.Text("Vision", size=9, weight=ft.FontWeight.BOLD, color=T.ACCENT_LIGHT),
                    ],
                    spacing=3,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=T.ACCENT_DIM,
                border=ft.border.all(1, T.BORDER_ACCENT),
                border_radius=4,
                padding=ft.padding.symmetric(horizontal=5, vertical=2),
                visible=is_vision,
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

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            entry["label"],
                                            size=13,
                                            weight=ft.FontWeight.W_600,
                                            color=T.TEXT_PRIMARY,
                                        ),
                                        vision_badge,
                                        ft.Text(
                                            f"{entry['size_gb']} GB",
                                            size=11,
                                            color=T.TEXT_MUTED,
                                        ),
                                    ],
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(entry["description"], size=11, color=T.TEXT_SECONDARY),
                                tags_row,
                                ft.Text(
                                    ref=status_ref,
                                    value="Installed ✓" if installed else "",
                                    size=11,
                                    color=T.SUCCESS,
                                    italic=True,
                                ),
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
                border=ft.border.all(1, T.SUCCESS if installed else T.BORDER),
            )

        def _category_header(cat: str) -> ft.Container:
            meta = _CATEGORY_META.get(cat, {"label": cat.title(), "desc": ""})
            icon_map = {
                "vision":    ft.Icons.IMAGE_OUTLINED,
                "chat":      ft.Icons.CHAT_BUBBLE_OUTLINE,
                "reasoning": ft.Icons.PSYCHOLOGY_OUTLINED,
                "code":      ft.Icons.CODE,
            }
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(icon_map.get(cat, ft.Icons.WIDGETS_OUTLINED), size=14, color=T.ACCENT_LIGHT),
                                ft.Text(meta["label"], size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(meta.get("desc", ""), size=11, color=T.TEXT_MUTED),
                    ],
                    spacing=2,
                    tight=True,
                ),
                padding=ft.padding.only(top=8, bottom=2),
            )

        # Group catalog by category
        by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
        for entry in CATALOG:
            cat = entry.get("category", "chat")
            by_cat.setdefault(cat, []).append(entry)

        grouped_controls: list[ft.Control] = []
        for cat in CATEGORY_ORDER:
            entries = by_cat.get(cat, [])
            if not entries:
                continue
            grouped_controls.append(_category_header(cat))
            for entry in entries:
                grouped_controls.append(_make_model_card(entry))

        # ── Ollama status bar ──────────────────────────────────────────────
        installed_app      = is_ollama_installed()
        ollama_status_ref  = ft.Ref[ft.Text]()
        ollama_badge_ref   = ft.Ref[ft.Container]()
        install_btn_ref    = ft.Ref[ft.ElevatedButton]()
        start_btn_ref      = ft.Ref[ft.ElevatedButton]()

        def _refresh_ollama_state(is_running: bool):
            _debounced_rebuild(self.app, self.app.state, delay=0.2)

        def on_install(e):
            install_btn_ref.current.disabled = True
            install_btn_ref.current.text = "Installing…"
            ollama_status_ref.current.value = "Downloading installer…"
            self.page.update()
            def run():
                def on_status(msg):
                    ollama_status_ref.current.value = msg
                    try: self.page.update()
                    except Exception: pass
                ok = install_ollama(on_status=on_status)
                if not ok:
                    on_status("Install failed — try manually at ollama.com/download")
                _refresh_ollama_state(is_ollama_running())
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
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=T.ACCENT_LIGHT),
                            ft.Text(
                                "Ollama is not running",
                                size=12,
                                color=T.TEXT_SECONDARY,
                                weight=ft.FontWeight.W_600,
                            ),
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
                        ft.Text(
                            "Local Models",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=T.TEXT_PRIMARY,
                        ),
                        ft.Container(expand=True),
                        ft.Container(
                            ref=ollama_badge_ref,
                            content=ft.Text(
                                ref=ollama_status_ref,
                                value=initial_status_text,
                                size=11,
                                color=status_color,
                                weight=ft.FontWeight.W_600,
                            ),
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
                *grouped_controls,
            ],
            spacing=8,
            tight=True,
        )

    def _build_local_image_section(self) -> ft.Column:
        """Ollama-style download cards for local image generation models."""
        from storage.settings_repo import get_setting, set_setting
        from ai_providers.local_image_provider import (
            download_model, delete_model as delete_img_model,
        )

        hf_token_saved = get_setting("imggen_hf_token", "")
        model_saved    = get_setting("imggen_model", "")
        steps_saved    = get_setting("imggen_steps", "25")
        width_saved    = get_setting("imggen_width", "768")
        height_saved   = get_setting("imggen_height", "768")
        cfg_saved      = get_setting("imggen_cfg", "7.0")

        # ── Dependency check (cached; background thread refreshes stale data) ──
        img_state = _IMGDEPS_STATE
        now = _time.time()
        use_img_cache = img_state["ts"] > 0 and (now - img_state["ts"]) < _CACHE_TTL

        if not use_img_cache and not img_state["checking"]:
            img_state["checking"] = True

            def _bg_imgdeps(app=self.app, view_state=self.app.state):
                from ai_providers.local_image_provider import get_installed_models as _gim, check_deps as _cd, get_gpu_info as _ggi
                _IMGDEPS_STATE["deps"] = _cd()
                _IMGDEPS_STATE["installed_ids"] = _gim()
                _IMGDEPS_STATE["gpu"] = _ggi()
                _IMGDEPS_STATE["ts"] = _time.time()
                _IMGDEPS_STATE["checking"] = False
                _debounced_rebuild(app, view_state)

            threading.Thread(target=_bg_imgdeps, daemon=True).start()

        deps = img_state["deps"]
        missing_pkgs = [p for p, ok in deps.items() if not ok]
        deps_ok = not missing_pkgs and bool(deps)
        # Download only needs huggingface_hub; torch/diffusers are for generation.
        # If deps haven't been checked yet (empty dict), allow download optimistically.
        can_download = deps.get("huggingface_hub", True)

        # GPU info — use cache or detect synchronously (fast: reads torch / nvidia-smi)
        gpu_info: dict = img_state.get("gpu") or {}
        if not gpu_info:
            gpu_info = get_gpu_info()
            img_state["gpu"] = gpu_info

        # ── GPU info box ─────────────────────────────────────────────────────────
        _gpu_vram  = gpu_info.get("vram_gb")
        _gpu_name  = gpu_info.get("name", "")
        _gpu_dev   = gpu_info.get("device", "cpu")
        _WARN_CLR  = "#f59e0b"
        _WARN_BG   = "#451a03"
        _WARN_BDR  = "#92400e"

        if _gpu_dev == "cuda" and _gpu_vram and _gpu_vram > 0:
            _gpu_color = T.SUCCESS if _gpu_vram >= 8 else _WARN_CLR
            _gpu_bg    = "#052e16" if _gpu_vram >= 8 else _WARN_BG
            _gpu_bdr   = T.SUCCESS if _gpu_vram >= 8 else _WARN_BDR
            _gpu_text  = f"GPU: {_gpu_name}  ·  {_gpu_vram:.0f} GB VRAM"
            _gpu_icon  = ft.Icons.MEMORY
        elif _gpu_dev == "mps":
            _vram_str  = f"  ·  {_gpu_vram:.0f} GB" if _gpu_vram else ""
            _gpu_color = T.SUCCESS
            _gpu_bg    = "#052e16"
            _gpu_bdr   = T.SUCCESS
            _gpu_text  = f"GPU: {_gpu_name}{_vram_str}  (Apple Silicon)"
            _gpu_icon  = ft.Icons.MEMORY
        else:
            _gpu_color = _WARN_CLR
            _gpu_bg    = _WARN_BG
            _gpu_bdr   = _WARN_BDR
            _gpu_text  = "No GPU detected — models will run on CPU (very slow)"
            _gpu_icon  = ft.Icons.WARNING_AMBER_OUTLINED

        gpu_box = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(_gpu_icon, size=14, color=_gpu_color),
                    ft.Text(_gpu_text, size=11, color=_gpu_color),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=_gpu_bg,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, _gpu_bdr),
        )

        _gen_pkgs_missing = [p for p in missing_pkgs if p != "huggingface_hub"]
        _hub_missing      = "huggingface_hub" in missing_pkgs
        _checking         = not bool(deps)

        if _checking:
            _deps_icon    = ft.Icons.SYNC_OUTLINED
            _deps_color   = T.TEXT_MUTED
            _deps_text    = "Checking packages…"
            _deps_rows    = []
        elif _hub_missing:
            _deps_icon    = ft.Icons.ERROR_OUTLINE
            _deps_color   = "#f59e0b"
            _deps_text    = "huggingface_hub not installed — required to download models"
            _hub_btn, _hub_stat = self._make_install_btn(["huggingface_hub"], "huggingface_hub")
            _deps_rows    = [ft.Row(controls=[_hub_btn, _hub_stat], spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        elif _gen_pkgs_missing:
            _deps_icon    = ft.Icons.WARNING_AMBER_OUTLINED
            _deps_color   = "#f59e0b"
            _deps_text    = f"Generation packages missing: {', '.join(_gen_pkgs_missing)}"
            _gen_btn, _gen_stat = self._make_install_btn(
                ["diffusers", "transformers", "accelerate", "torch"], "generation packages"
            )
            _deps_rows    = [
                ft.Text("Download works. Install below to enable image generation:",
                        size=11, color=T.TEXT_MUTED),
                ft.Row(controls=[_gen_btn, _gen_stat], spacing=10,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ]
        else:
            _deps_icon    = ft.Icons.CHECK_CIRCLE_OUTLINED
            _deps_color   = T.SUCCESS
            _deps_text    = "All packages installed ✓"
            _deps_rows    = []

        deps_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(_deps_icon, size=14, color=_deps_color),
                            ft.Text(_deps_text, size=12, color=_deps_color,
                                    weight=ft.FontWeight.W_500),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    *_deps_rows,
                ],
                spacing=6, tight=True,
            ),
            bgcolor=T.BG_SECONDARY, border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border=ft.border.all(1, _deps_color),
        )

        installed_ids = img_state["installed_ids"]

        # ── HuggingFace token ────────────────────────────────────────────────
        hf_token_field = ft.TextField(
            value=hf_token_saved,
            hint_text="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            password=True,
            can_reveal_password=True,
            bgcolor=T.BG_INPUT, border_color=T.BORDER,
            focused_border_color=T.ACCENT, color=T.TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
            cursor_color=T.ACCENT_LIGHT, border_radius=8,
            text_size=12, expand=True,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
        )
        hf_save_badge = ft.Text("", size=11, color=T.SUCCESS)

        def on_save_hf_token(e):
            set_setting("imggen_hf_token", hf_token_field.value.strip())
            hf_save_badge.value = "Saved ✓"
            try:
                hf_save_badge.update()
            except Exception:
                pass

        # ── Generation settings ──────────────────────────────────────────────
        def _num_field(value: str, hint: str, width: int = 80) -> ft.TextField:
            return ft.TextField(
                value=value, hint_text=hint,
                bgcolor=T.BG_INPUT, border_color=T.BORDER,
                focused_border_color=T.ACCENT, color=T.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
                cursor_color=T.ACCENT_LIGHT, border_radius=8,
                text_size=12, width=width,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
            )

        model_opts     = [ft.dropdown.Option("", "— auto (first installed) —")]
        model_opts    += [ft.dropdown.Option(mid, mid) for mid in installed_ids]
        model_dd       = ft.Dropdown(
            value=model_saved if model_saved in installed_ids else "",
            options=model_opts,
            bgcolor=T.BG_INPUT, border_color=T.BORDER,
            focused_border_color=T.ACCENT, color=T.TEXT_PRIMARY,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8, expand=True,
        )
        steps_field    = _num_field(steps_saved,  "25")
        width_field    = _num_field(width_saved,  "768")
        height_field   = _num_field(height_saved, "768")
        cfg_field      = _num_field(cfg_saved,    "7.0")
        gen_save_badge = ft.Text("", size=11, color=T.SUCCESS)

        def on_save_gen(e):
            set_setting("imggen_model", (model_dd.value or "").strip())
            try:
                set_setting("imggen_steps",  str(int(steps_field.value or "25")))
                set_setting("imggen_width",  str(int(width_field.value or "768")))
                set_setting("imggen_height", str(int(height_field.value or "768")))
                set_setting("imggen_cfg",    str(float(cfg_field.value or "7.0")))
            except ValueError:
                pass
            gen_save_badge.value = "Saved ✓"
            try:
                gen_save_badge.update()
            except Exception:
                pass

        # ── Model download cards ─────────────────────────────────────────────
        def _tier_header(tier: str) -> ft.Container:
            label  = _TIER_LABELS.get(tier, tier)
            colors = {"high": T.ACCENT_LIGHT, "mid": T.TEXT_SECONDARY, "base": T.TEXT_MUTED}
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.STAR_OUTLINED, size=13, color=colors.get(tier, T.TEXT_MUTED)),
                        ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=colors.get(tier, T.TEXT_MUTED)),
                    ],
                    spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=8, bottom=2),
            )

        def _make_model_card(entry: dict) -> ft.Container:
            mid        = entry["id"]
            installed  = mid in installed_ids
            btn_ref    = ft.Ref[ft.ElevatedButton]()
            stat_ref   = ft.Ref[ft.Text]()
            gated      = entry.get("hf_gated", False)
            model_vram = entry["vram_gb"]
            user_vram  = _gpu_vram  # from outer scope

            # True when we know the user's VRAM and it's less than what the model needs
            vram_warn  = (user_vram is not None and user_vram < model_vram)

            def _start_download(model_id, btn, stat):
                btn.current.disabled = True
                btn.current.text = "Downloading…"
                stat.current.value = "Starting download…"
                try:
                    self.page.update()
                except Exception:
                    pass

                def run():
                    def on_prog(msg):
                        stat.current.value = msg
                        try:
                            self.page.update()
                        except Exception:
                            pass
                    ok = download_model(model_id, on_progress=on_prog)
                    if ok:
                        stat.current.value = "Installed ✓"
                        btn.current.text   = "Installed"
                    else:
                        stat.current.value = stat.current.value
                        btn.current.disabled = False
                        btn.current.text   = "Download"
                    try:
                        self.page.update()
                    except Exception:
                        pass
                threading.Thread(target=run, daemon=True).start()

            def make_download(model_id=mid, btn=btn_ref, stat=stat_ref,
                              vw=vram_warn, m_vram=model_vram, u_vram=user_vram,
                              entry_label=entry["label"]):
                def do_download(e):
                    if not vw:
                        _start_download(model_id, btn, stat)
                        return

                    # ── Hardware warning dialog ────────────────────────────────
                    if u_vram == 0.0:
                        warn_title = "No GPU Detected"
                        warn_body  = (
                            f"{entry_label} requires {m_vram} GB of GPU VRAM, "
                            "but no GPU was found on this machine.\n\n"
                            "The model will run on CPU and generation will be "
                            "extremely slow (minutes per image). Download anyway?"
                        )
                    else:
                        warn_title = "Insufficient VRAM"
                        warn_body  = (
                            f"{entry_label} requires {m_vram} GB VRAM but your "
                            f"GPU ({_gpu_name}) only has {u_vram:.0f} GB.\n\n"
                            "The model may fail to load or run very slowly with "
                            "CPU offloading. Download anyway?"
                        )

                    def proceed(ev):
                        _warn_dlg.open = False
                        try:
                            self.page.update()
                        except Exception:
                            pass
                        _start_download(model_id, btn, stat)

                    def cancel_dl(ev):
                        _warn_dlg.open = False
                        try:
                            self.page.update()
                        except Exception:
                            pass

                    _warn_dlg = ft.AlertDialog(
                        modal=True,
                        title=ft.Text(
                            warn_title, size=15, weight=ft.FontWeight.BOLD,
                            color=_WARN_CLR,
                        ),
                        bgcolor=T.BG_CARD,
                        content=ft.Text(warn_body, size=13, color=T.TEXT_SECONDARY),
                        actions=[
                            ft.TextButton(
                                "Cancel", on_click=cancel_dl,
                                style=ft.ButtonStyle(color=T.TEXT_MUTED),
                            ),
                            ft.ElevatedButton(
                                "Download Anyway",
                                on_click=proceed,
                                style=ft.ButtonStyle(
                                    bgcolor={"": _WARN_BDR, "disabled": T.BG_SECONDARY},
                                    color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                            ),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    )
                    self.page.overlay.clear()
                    self.page.overlay.append(_warn_dlg)
                    _warn_dlg.open = True
                    try:
                        self.page.update()
                    except Exception:
                        pass

                return do_download

            def make_delete(model_id=mid, btn=btn_ref, stat=stat_ref):
                def do_delete(e):
                    stat.current.value = "Deleting…"
                    try:
                        self.page.update()
                    except Exception:
                        pass
                    ok = delete_img_model(model_id)
                    if ok:
                        stat.current.value = ""
                        btn.current.text   = "Download"
                        btn.current.on_click = make_download(model_id, btn, stat)
                        btn.current.style = ft.ButtonStyle(
                            bgcolor={"": T.ACCENT if deps_ok else T.BG_SECONDARY, "disabled": T.BG_SECONDARY},
                            color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        )
                    else:
                        stat.current.value = "Delete failed"
                    try:
                        self.page.update()
                    except Exception:
                        pass
                return do_delete

            if installed:
                btn_text     = "Installed"
                btn_disabled = False
                btn_color    = T.SUCCESS
                btn_click    = make_delete()
            else:
                btn_text     = "Download"
                btn_disabled = not can_download
                btn_color    = T.ACCENT if can_download else T.BG_SECONDARY
                btn_click    = make_download()

            action_btn = ft.ElevatedButton(
                ref=btn_ref,
                text=btn_text,
                disabled=btn_disabled,
                on_click=btn_click,
                style=ft.ButtonStyle(
                    bgcolor={"": btn_color, "disabled": T.BG_SECONDARY},
                    color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                ),
            )

            tags_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(t, size=10, color=T.ACCENT_LIGHT),
                        bgcolor=T.BG_SECONDARY, border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border=ft.border.all(1, T.BORDER),
                    )
                    for t in entry.get("tags", [])
                ],
                spacing=4, wrap=True,
            )

            note = entry.get("install_note", "")
            note_controls = []
            if gated and note:
                note_controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LOCK_OUTLINED, size=10, color=T.TEXT_MUTED),
                            ft.Text(note, size=10, color=T.TEXT_MUTED, expand=True),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

            # VRAM warning badge shown inline with the VRAM label
            vram_color = _WARN_CLR if vram_warn else T.TEXT_MUTED
            vram_label_controls = [
                ft.Text(entry["label"], size=13,
                        weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                ft.Text(f"{entry['size_gb']} GB", size=11, color=T.TEXT_MUTED),
                ft.Text(f"{entry['vram_gb']} GB VRAM", size=11, color=vram_color),
            ]
            if vram_warn:
                vram_label_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=10, color=_WARN_CLR),
                                ft.Text("needs more VRAM", size=9, color=_WARN_CLR),
                            ],
                            spacing=3, tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=_WARN_BG,
                        border=ft.border.all(1, _WARN_BDR),
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    )
                )

            card_border_color = T.SUCCESS if installed else (_WARN_BDR if vram_warn else T.BORDER)

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=vram_label_controls,
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(entry["description"], size=11, color=T.TEXT_SECONDARY),
                                tags_row,
                                *note_controls,
                                ft.Text(
                                    ref=stat_ref,
                                    value="Installed ✓" if installed else "",
                                    size=11, color=T.SUCCESS, italic=True,
                                ),
                            ],
                            spacing=3, expand=True, tight=True,
                        ),
                        action_btn,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=T.BG_CARD, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                border=ft.border.all(1, card_border_color),
            )

        # Group catalog by tier
        tier_order = ["high", "mid", "base"]
        by_tier: dict[str, list] = {t: [] for t in tier_order}
        for entry in IMAGE_MODEL_CATALOG:
            by_tier.setdefault(entry["tier"], []).append(entry)

        model_cards: list[ft.Control] = []
        for tier in tier_order:
            entries = by_tier.get(tier, [])
            if not entries:
                continue
            model_cards.append(_tier_header(tier))
            for entry in entries:
                model_cards.append(_make_model_card(entry))

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=T.ACCENT_LIGHT),
                        ft.Text("Local Image Models", size=15,
                                weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Text(
                                f"{len(installed_ids)} installed",
                                size=11,
                                color=T.SUCCESS if installed_ids else T.TEXT_MUTED,
                                weight=ft.FontWeight.W_600,
                            ),
                            bgcolor="#052e16" if installed_ids else T.BG_SECONDARY,
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border=ft.border.all(1, T.SUCCESS if installed_ids else T.BORDER),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Download image generation models once — run fully offline. "
                    "No external servers, no API keys.",
                    size=12, color=T.TEXT_MUTED,
                ),
                ft.Container(height=4),
                gpu_box,
                ft.Container(height=2),
                deps_box,
                ft.Container(height=4),
                # HuggingFace token
                ft.Text("HuggingFace Token", size=12, color=T.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    "Required for gated models (FLUX.1 Dev/Schnell, FLUX.2 [klein] 9B, SD 3.5). "
                    "Free account at huggingface.co → Settings → Access Tokens.",
                    size=11, color=T.TEXT_MUTED,
                ),
                ft.Row(
                    controls=[hf_token_field,
                               ft.TextButton("Get token", url="https://huggingface.co/settings/tokens",
                                             style=ft.ButtonStyle(color=T.TEXT_ACCENT))],
                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        T.accent_button("Save Token", on_click=on_save_hf_token,
                                        icon=ft.Icons.SAVE_OUTLINED),
                        hf_save_badge,
                    ],
                    spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=8),
                # Generation settings
                ft.Text("Generation Settings", size=12, color=T.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600),
                ft.Row(
                    controls=[
                        ft.Text("Active model", size=11, color=T.TEXT_MUTED, width=100),
                        model_dd,
                    ],
                    spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Steps", size=11, color=T.TEXT_MUTED, width=100),
                        steps_field,
                        ft.Text("CFG Scale", size=11, color=T.TEXT_MUTED),
                        cfg_field,
                    ],
                    spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Width × Height", size=11, color=T.TEXT_MUTED, width=100),
                        width_field,
                        ft.Text("×", size=12, color=T.TEXT_MUTED),
                        height_field,
                        ft.Text("px", size=11, color=T.TEXT_MUTED),
                    ],
                    spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        T.accent_button("Save Settings", on_click=on_save_gen,
                                        icon=ft.Icons.SAVE_OUTLINED),
                        gen_save_badge,
                    ],
                    spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=8),
                ft.Text("Models", size=12, color=T.TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                *model_cards,
            ],
            spacing=8,
        )

    def _build_cloud_media_section(self) -> ft.Column:
        """Cards for cloud image and video generation APIs."""
        from storage.settings_repo import get_setting, set_setting
        from storage.asset_repo import save_api_key, get_all_api_keys

        existing_keys = get_all_api_keys()

        def _make_service_card(entry: dict) -> ft.Container:
            key_name    = entry["setting_key"]
            is_shared   = key_name in ("openai", "claude", "gemini")
            configured  = bool(existing_keys.get(key_name, "").strip())

            tag_chips = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(t, size=10, color=T.ACCENT_LIGHT),
                        bgcolor=T.BG_SECONDARY,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border=ft.border.all(1, T.BORDER),
                    )
                    for t in entry.get("tags", [])
                ],
                spacing=4, wrap=True,
            )

            key_row_controls: list = []
            save_badge = ft.Text("", size=11, color=T.SUCCESS)

            if not is_shared:
                tf = ft.TextField(
                    label=f"{entry['label']} API Key",
                    value=("•" * 8 + existing_keys[key_name][-4:])
                          if len(existing_keys.get(key_name, "")) > 8
                          else existing_keys.get(key_name, ""),
                    password=True,
                    can_reveal_password=True,
                    hint_text="Enter API key",
                    bgcolor=T.BG_INPUT, border_color=T.BORDER,
                    focused_border_color=T.ACCENT, color=T.TEXT_PRIMARY,
                    label_style=ft.TextStyle(color=T.TEXT_MUTED),
                    hint_style=ft.TextStyle(color=T.TEXT_MUTED),
                    cursor_color=T.ACCENT_LIGHT, border_radius=8,
                    content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    expand=True,
                )

                def make_save(k=key_name, field=tf, badge=save_badge):
                    def do_save(e):
                        val = field.value.strip()
                        if val and not all(c == "•" for c in val):
                            save_api_key(k, val)
                            badge.value = "Saved ✓"
                            try:
                                badge.update()
                            except Exception:
                                pass
                    return do_save

                key_row_controls = [
                    ft.Row(
                        controls=[
                            tf,
                            ft.TextButton(
                                "Get Key",
                                url=entry["api_url"],
                                style=ft.ButtonStyle(color=T.TEXT_ACCENT),
                            ),
                            ft.ElevatedButton(
                                "Save",
                                on_click=make_save(),
                                style=ft.ButtonStyle(
                                    bgcolor={"": T.ACCENT, "disabled": T.BG_SECONDARY},
                                    color={"": "#ffffff", "disabled": T.TEXT_MUTED},
                                    shape=ft.RoundedRectangleBorder(radius=6),
                                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                ),
                            ),
                            save_badge,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ]
            else:
                key_row_controls = [
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_OUTLINED if configured else ft.Icons.INFO_OUTLINE,
                                size=13,
                                color=T.SUCCESS if configured else T.TEXT_MUTED,
                            ),
                            ft.Text(
                                f"Uses your {key_name.title()} API key (configured above)"
                                if configured
                                else f"Add your {key_name.title()} key above to enable this",
                                size=11,
                                color=T.SUCCESS if configured else T.TEXT_MUTED,
                            ),
                            ft.TextButton(
                                "Docs",
                                url=entry["docs_url"],
                                style=ft.ButtonStyle(color=T.TEXT_ACCENT),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ]

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            entry["label"],
                                            size=13, weight=ft.FontWeight.W_600,
                                            color=T.TEXT_PRIMARY,
                                        ),
                                        ft.Text(
                                            entry["description"],
                                            size=11, color=T.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            entry["pricing_note"],
                                            size=10, color=T.TEXT_MUTED, italic=True,
                                        ),
                                        tag_chips,
                                    ],
                                    spacing=3, expand=True, tight=True,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "Ready" if configured else "Key needed",
                                        size=10,
                                        color=T.SUCCESS if configured else T.TEXT_MUTED,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    bgcolor="#052e16" if configured else T.BG_SECONDARY,
                                    border_radius=5,
                                    padding=ft.padding.symmetric(horizontal=7, vertical=3),
                                    border=ft.border.all(1, T.SUCCESS if configured else T.BORDER),
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        *key_row_controls,
                    ],
                    spacing=8,
                    tight=True,
                ),
                bgcolor=T.BG_CARD, border_radius=10,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border=ft.border.all(1, T.SUCCESS if configured else T.BORDER),
            )

        def _section_header(label: str, icon) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=14, color=T.ACCENT_LIGHT),
                        ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=8, bottom=2),
            )

        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOUD_OUTLINED, size=16, color=T.ACCENT_LIGHT),
                    ft.Text("Cloud Image & Video APIs", size=15,
                            weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(
                "Connect third-party cloud services for image and video generation. "
                "Shared keys (OpenAI, Gemini) are already configured above.",
                size=12, color=T.TEXT_MUTED,
            ),
            ft.Container(height=4),
            _section_header(_CLOUD_CATEGORY_LABELS["image"], ft.Icons.IMAGE_OUTLINED),
        ]
        for entry in CLOUD_IMAGE_CATALOG:
            controls.append(_make_service_card(entry))

        controls.append(_section_header(_CLOUD_CATEGORY_LABELS["video"], ft.Icons.VIDEOCAM_OUTLINED))
        for entry in CLOUD_VIDEO_CATALOG:
            controls.append(_make_service_card(entry))

        return ft.Column(controls=controls, spacing=8, tight=True)

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

