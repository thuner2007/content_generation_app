"""Design tokens and shared style helpers for the UI."""
import flet as ft

# ── Colours ────────────────────────────────────────────────────────────────────
BG_PRIMARY    = "#0d0d1a"
BG_SECONDARY  = "#11111f"
BG_SIDEBAR    = "#0a0a16"
BG_CARD       = "#1a1a2e"
BG_CARD_HOVER = "#20203a"
BG_INPUT      = "#1a1a2e"
BG_USER_MSG   = "#1e3a5f"
BG_AI_MSG     = "#151528"

ACCENT        = "#7c3aed"
ACCENT_LIGHT  = "#a78bfa"
ACCENT_HOVER  = "#6d28d9"
ACCENT_DIM    = "#3d1f7a"

TEXT_PRIMARY   = "#e2e8f0"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED     = "#64748b"
TEXT_ACCENT    = "#a78bfa"

BORDER        = "#2a2a45"
BORDER_ACCENT = "#4c2a9a"

SUCCESS       = "#10b981"
ERROR         = "#ef4444"
WARNING       = "#f59e0b"
INFO          = "#3b82f6"

SIDEBAR_WIDTH  = 230
PANEL_WIDTH    = 290

# ── Text Styles ────────────────────────────────────────────────────────────────

def h1(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=22, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, **kwargs)

def h2(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, **kwargs)

def h3(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY, **kwargs)

def body(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=13, color=TEXT_PRIMARY, **kwargs)

def muted(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=11, color=TEXT_MUTED, **kwargs)

def caption(text: str, **kwargs) -> ft.Text:
    return ft.Text(text, size=11, color=TEXT_SECONDARY, **kwargs)

# ── Common Widgets ─────────────────────────────────────────────────────────────

def divider(vertical: bool = False) -> ft.Control:
    if vertical:
        return ft.VerticalDivider(width=1, color=BORDER)
    return ft.Divider(height=1, color=BORDER)


def section_label(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(
            text.upper(),
            size=10,
            weight=ft.FontWeight.W_700,
            color=TEXT_MUTED,
            style=ft.TextStyle(letter_spacing=1.2),
        ),
        padding=ft.padding.only(left=12, top=16, bottom=6),
    )


def icon_button(
    icon: str,
    tooltip: str,
    on_click=None,
    color: str = TEXT_SECONDARY,
    size: int = 18,
) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        tooltip=tooltip,
        on_click=on_click,
        icon_color=color,
        icon_size=size,
        style=ft.ButtonStyle(
            overlay_color={"": ft.Colors.TRANSPARENT, "hovered": ACCENT_DIM},
        ),
    )


def accent_button(text: str, on_click=None, icon: str | None = None, width: int | None = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        width=width,
        style=ft.ButtonStyle(
            bgcolor={"": ACCENT, "hovered": ACCENT_HOVER, "disabled": BORDER},
            color={"": "#ffffff", "disabled": TEXT_MUTED},
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        ),
    )


def text_button(text: str, on_click=None) -> ft.TextButton:
    return ft.TextButton(
        text=text,
        on_click=on_click,
        style=ft.ButtonStyle(color=TEXT_ACCENT),
    )


def card(content: ft.Control, padding: int = 14, expand: bool = False) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=BG_CARD,
        border_radius=10,
        padding=padding,
        border=ft.border.all(1, BORDER),
        expand=expand,
    )


def styled_textfield(
    label: str,
    value: str = "",
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: int = 1,
    password: bool = False,
    on_change=None,
    hint: str = "",
    expand: bool = False,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines if multiline else 1,
        password=password,
        can_reveal_password=password,
        on_change=on_change,
        hint_text=hint,
        expand=expand,
        bgcolor=BG_INPUT,
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED),
        hint_style=ft.TextStyle(color=TEXT_MUTED),
        cursor_color=ACCENT_LIGHT,
        border_radius=8,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
    )


def provider_badge(provider: str) -> ft.Container:
    colors = {
        "openai": ("#10b981", "#052e16"),
        "claude": ("#f97316", "#431407"),
        "gemini": ("#3b82f6", "#1e3a8a"),
    }
    text_color, bg = colors.get(provider, (TEXT_MUTED, BG_CARD))
    return ft.Container(
        content=ft.Text(provider.capitalize(), size=10, color=text_color, weight=ft.FontWeight.W_600),
        bgcolor=bg,
        border_radius=4,
        padding=ft.padding.symmetric(horizontal=6, vertical=2),
        border=ft.border.all(1, text_color),
    )
