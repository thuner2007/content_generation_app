"""
AI Ads & Content Generation Studio
Entry point — run with:  python main.py
Package with:            flet pack main.py --name "AI Ads Studio"
"""
import flet as ft

from app_bootstrap import bootstrap
from ui.layout import AppLayout
from ui import theme as T


def main(page: ft.Page) -> None:
    # ── Bootstrap ──────────────────────────────────────────────────────────────
    bootstrap()

    # ── Window configuration ───────────────────────────────────────────────────
    page.title = "AI Ads & Content Generation Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = T.BG_PRIMARY
    page.padding = 0
    page.spacing = 0

    page.window.width = 1440
    page.window.height = 900
    page.window.min_width = 1000
    page.window.min_height = 680
    page.window.center()

    # ── Custom dark theme ──────────────────────────────────────────────────────
    page.theme = ft.Theme(
        color_scheme_seed=T.ACCENT,
        font_family="Segoe UI",
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary=T.ACCENT,
            on_primary="#ffffff",
            secondary=T.ACCENT_LIGHT,
            background=T.BG_PRIMARY,
            surface=T.BG_CARD,
            on_surface=T.TEXT_PRIMARY,
        ),
    )

    # ── Build and render ───────────────────────────────────────────────────────
    app = AppLayout(page=page)
    page.add(app.build())


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
