"""Campaigns — left panel lists campaigns, right panel shows product + ad schedule."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import flet as ft

from ui import theme as T
from storage import campaign_repo, product_repo
from storage.models import Campaign, Product
from ai_providers.ollama_provider import OllamaProvider, is_ollama_running, list_installed_models
from ai_providers.router import get_provider, get_configured_providers

if TYPE_CHECKING:
    from ui.layout import AppLayout

# ── Lookup tables ──────────────────────────────────────────────────────────────

_STRATEGIES = [
    ("awareness",   "Awareness",      ft.Icons.VISIBILITY_OUTLINED,      "Reach new audiences & build brand recognition"),
    ("conversion",  "Conversion",     ft.Icons.SHOPPING_CART_OUTLINED,   "Drive purchases, sign-ups, or installs"),
    ("retargeting", "Retargeting",    ft.Icons.LOOP,                     "Re-engage warm audiences & past visitors"),
    ("lead_gen",    "Lead Gen",       ft.Icons.PERSON_ADD_OUTLINED,      "Collect leads via forms or landing pages"),
    ("brand",       "Brand Building", ft.Icons.STAR_BORDER,              "Long-term equity and audience recall"),
    ("retention",   "Retention",      ft.Icons.FAVORITE_BORDER,          "Keep existing customers coming back"),
]

_PLATFORMS = [
    ("meta",      "Meta",      "#1877F2"),
    ("google",    "Google",    "#4285F4"),
    ("tiktok",    "TikTok",    "#EE1D52"),
    ("linkedin",  "LinkedIn",  "#0A66C2"),
    ("youtube",   "YouTube",   "#FF0000"),
    ("pinterest", "Pinterest", "#E60023"),
    ("snapchat",  "Snapchat",  "#FFCD00"),
    ("x",         "X/Twitter", "#1DA1F2"),
]

_OBJECTIVES = [
    ("traffic",      "Traffic",      ft.Icons.OPEN_IN_NEW),
    ("leads",        "Leads",        ft.Icons.MAIL_OUTLINE),
    ("sales",        "Sales",        ft.Icons.ATTACH_MONEY),
    ("awareness",    "Awareness",    ft.Icons.VISIBILITY_OUTLINED),
    ("engagement",   "Engagement",   ft.Icons.THUMB_UP_OUTLINED),
    ("app_installs", "App Installs", ft.Icons.PHONE_ANDROID_OUTLINED),
    ("video_views",  "Video Views",  ft.Icons.PLAY_CIRCLE_OUTLINE),
]

_STATUS_COLOR = {
    "draft":     T.TEXT_MUTED,
    "active":    T.SUCCESS,
    "paused":    T.WARNING,
    "completed": T.INFO,
}
_STATUS_ICON = {
    "draft":     ft.Icons.EDIT_OUTLINED,
    "active":    ft.Icons.PLAY_CIRCLE_OUTLINE,
    "paused":    ft.Icons.PAUSE_CIRCLE_OUTLINE,
    "completed": ft.Icons.CHECK_CIRCLE_OUTLINE,
}

_STRATEGY_LABELS = {k: v for k, v, *_ in _STRATEGIES}
_OBJECTIVE_LABELS = {k: v for k, v, *_ in _OBJECTIVES}
_PLATFORM_COLORS  = {k: c for k, _, c in _PLATFORMS}
_PLATFORM_LABELS  = {k: v for k, v, _ in _PLATFORMS}

_AD_FORMATS = [
    ("reel",     "Reel"),
    ("story",    "Story"),
    ("feed",     "Feed"),
    ("short",    "Short"),
    ("pre_roll", "Pre-roll"),
]

_PUB_STATUSES = [
    ("in_progress", "In Progress", T.WARNING,    "#2a1800",  T.WARNING),
    ("done",        "Done",        T.INFO,        "#001828",  T.INFO),
    ("posted",      "Posted",      T.SUCCESS,     "#0a2010",  T.SUCCESS),
]


class CampaignView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page  = page
        self.app   = app
        self.state = app.state

        self._selected: Campaign | None = None
        self._campaign_cards: dict[str, ft.Container] = {}

        self._idea_entries: list[dict] = []
        self._ideas_col = ft.Column(spacing=10)
        self._gen_btn: ft.ElevatedButton | None = None
        self._gen_stop_btn: ft.ElevatedButton | None = None
        self._gen_status: ft.Text | None = None
        self._gen_model_dd: ft.Dropdown | None = None
        self._gen_running: bool = False
        self._gen_stop_event: threading.Event | None = None
        self._gen_selected_provider: str = "ollama"
        self._gen_selected_model: str = ""
        self._gen_videos_per_day: int = 1
        self._gen_duration_days: int = 7
        self._gen_count_badge: ft.Text | None = None
        self._gen_vpd_chips: dict[int, ft.Container] = {}
        self._gen_dur_chips: dict[int, ft.Container] = {}
        self._gen_content_type: str = "mixed"
        self._gen_type_chips: dict[str, ft.Container] = {}

        # Calendar state
        self._cal_year: int = date.today().year
        self._cal_month: int = date.today().month
        self._cal_grid_container: ft.Container | None = None
        self._cal_header_text: ft.Text | None = None

        # Detail field refs (prefixed _d_)
        self._d_name_f: ft.TextField | None = None
        self._d_start_f: ft.TextField | None = None
        self._d_end_f: ft.TextField | None = None
        self._d_daily_f: ft.TextField | None = None
        self._d_total_f: ft.TextField | None = None
        self._d_audience_f: ft.TextField | None = None
        self._d_notes_f: ft.TextField | None = None
        self._d_product_name_f: ft.TextField | None = None
        self._d_product_desc_f: ft.TextField | None = None
        self._d_status_dd: ft.Dropdown | None = None
        self._d_strategy: str | None = None
        self._d_platforms: set[str] = set()
        self._d_objective: str | None = None
        self._d_strategy_chips: dict[str, ft.Container] = {}
        self._d_platform_chips: dict[str, ft.Container] = {}
        self._d_objective_chips: dict[str, ft.Container] = {}

        # Settings accordion state
        self._d_settings_expanded: bool = False
        self._d_settings_form: ft.Container | None = None
        self._d_settings_expand_icon: ft.Icon | None = None

        # Tab state
        self._d_tab: str = "products"
        self._d_tab_content: ft.Container | None = None
        self._d_tab_btns: dict[str, ft.Container] = {}

        # Product catalog (project-level, campaign just tracks which are promoted)
        self._d_product_ids: set[str] = set()

        # Create panel field refs (prefixed _c_)
        self._c_name_f: ft.TextField | None = None
        self._c_start_f: ft.TextField | None = None
        self._c_end_f: ft.TextField | None = None
        self._c_daily_f: ft.TextField | None = None
        self._c_total_f: ft.TextField | None = None
        self._c_audience_f: ft.TextField | None = None
        self._c_notes_f: ft.TextField | None = None
        self._c_strategy: str | None = None
        self._c_platforms: set[str] = set()
        self._c_objective: str | None = None
        self._c_strategy_chips: dict[str, ft.Container] = {}
        self._c_platform_chips: dict[str, ft.Container] = {}
        self._c_objective_chips: dict[str, ft.Container] = {}

        self._right = ft.Container(expand=5, bgcolor=T.BG_SECONDARY)
        self._list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self._stat_total:  ft.Text | None = None
        self._stat_active: ft.Text | None = None
        self._stat_paused: ft.Text | None = None

    # ── Public ─────────────────────────────────────────────────────────────────

    def build(self) -> ft.Row:
        self._reload_list()
        self._right.content = self._build_create_panel()
        return ft.Row(
            controls=[
                self._build_left(),
                ft.VerticalDivider(width=1, color=T.BORDER),
                self._right,
            ],
            expand=True,
            spacing=0,
        )

    # ── Left panel ──────────────────────────────────────────────────────────────

    def _build_left(self) -> ft.Container:
        campaigns = self._get_campaigns()
        total  = len(campaigns)
        active = sum(1 for c in campaigns if c.status == "active")
        paused = sum(1 for c in campaigns if c.status == "paused")

        self._stat_total  = ft.Text(str(total),  size=18, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY)
        self._stat_active = ft.Text(str(active), size=18, weight=ft.FontWeight.BOLD, color=T.SUCCESS)
        self._stat_paused = ft.Text(str(paused), size=18, weight=ft.FontWeight.BOLD, color=T.WARNING)

        project   = self.state.current_project
        proj_name = project.name if project else "All Projects"

        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.ROCKET_LAUNCH_OUTLINED, size=18, color=T.ACCENT_LIGHT),
                                width=38, height=38, bgcolor=T.ACCENT_DIM,
                                border_radius=10, alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Campaigns", size=17, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                    ft.Text(proj_name, size=11, color=T.TEXT_MUTED),
                                ],
                                spacing=1, tight=True, expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                tooltip="New Campaign",
                                icon_color=T.ACCENT_LIGHT,
                                icon_size=20,
                                on_click=lambda e: self._deselect(),
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                ),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            self._stat_chip("Total",  self._stat_total,  T.BORDER_ACCENT),
                            self._stat_chip("Active", self._stat_active, T.SUCCESS),
                            self._stat_chip("Paused", self._stat_paused, T.WARNING),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            bgcolor=T.BG_SECONDARY,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    T.divider(),
                    ft.Container(
                        content=self._list_col,
                        expand=True,
                        padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    ),
                ],
                spacing=0,
                expand=True,
            ),
            expand=3,
            bgcolor=T.BG_PRIMARY,
        )

    def _stat_chip(self, label: str, value_text: ft.Text, border_color: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[value_text, ft.Text(label, size=10, color=T.TEXT_MUTED)],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, border_color),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
        )

    def _reload_list(self) -> None:
        campaigns = self._get_campaigns()
        self._list_col.controls.clear()
        self._campaign_cards.clear()

        if not self.state.current_project:
            self._list_col.controls.append(self._empty_state(
                ft.Icons.BUSINESS_OUTLINED, "No project selected",
                "Select a project from the sidebar.",
            ))
        elif not campaigns:
            self._list_col.controls.append(self._empty_state(
                ft.Icons.ROCKET_LAUNCH_OUTLINED, "No campaigns yet",
                "Click + to create your first campaign.",
            ))
        else:
            for c in campaigns:
                card = self._campaign_card(c)
                self._campaign_cards[c.id] = card
                self._list_col.controls.append(card)

        try:
            self._list_col.update()
        except Exception:
            pass

    def _empty_state(self, icon, title: str, subtitle: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, size=44, color=T.TEXT_MUTED),
                    ft.Text(title, size=14, color=T.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                    ft.Text(subtitle, size=11, color=T.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.alignment.center,
            expand=True,
            padding=40,
        )

    def _campaign_card(self, c: Campaign) -> ft.Container:
        is_sel       = self._selected is not None and self._selected.id == c.id
        status_color = _STATUS_COLOR.get(c.status, T.TEXT_MUTED)
        status_icon  = _STATUS_ICON.get(c.status, ft.Icons.CIRCLE_OUTLINED)
        strategy_lbl = _STRATEGY_LABELS.get(c.strategy, "")
        platforms    = json.loads(c.platforms or "[]")

        plat_badges = [
            ft.Container(
                content=ft.Text(_PLATFORM_LABELS.get(p, p)[:2].upper(),
                                size=9, weight=ft.FontWeight.BOLD, color="#ffffff"),
                bgcolor=_PLATFORM_COLORS.get(p, T.ACCENT),
                border_radius=4,
                padding=ft.padding.symmetric(horizontal=5, vertical=2),
            )
            for p in platforms[:5]
        ]

        ideas_count = len(json.loads(c.video_ideas or "[]"))
        product_lbl = c.product_name[:28] + "…" if len(c.product_name) > 28 else c.product_name

        meta_row_controls: list[ft.Control] = [
            ft.Icon(status_icon, size=10, color=status_color),
            ft.Text(c.status.capitalize(), size=10, color=status_color),
        ]
        if strategy_lbl:
            meta_row_controls += [
                ft.Container(width=4),
                ft.Container(
                    content=ft.Text(strategy_lbl, size=9, color=T.ACCENT_LIGHT, weight=ft.FontWeight.W_600),
                    bgcolor=T.ACCENT_DIM, border_radius=3,
                    padding=ft.padding.symmetric(horizontal=5, vertical=1),
                ),
            ]

        def _on_click(e, campaign=c):
            self._select_campaign(campaign)

        def _on_rename(e):
            self._rename_campaign_dialog(c)

        def _on_delete(e):
            self._confirm_delete(c)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(width=3, height=36, bgcolor=status_color, border_radius=2),
                            ft.Column(
                                controls=[
                                    ft.Text(c.name, size=13, weight=ft.FontWeight.W_600,
                                            color=T.TEXT_PRIMARY, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Row(controls=meta_row_controls, spacing=3),
                                ],
                                spacing=2, tight=True, expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
                                icon_size=14, icon_color=T.TEXT_MUTED,
                                tooltip="Rename",
                                on_click=_on_rename,
                                style=ft.ButtonStyle(
                                    overlay_color={"":  ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                    padding=ft.padding.all(4),
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=14, icon_color=T.ERROR,
                                tooltip="Delete",
                                on_click=_on_delete,
                                style=ft.ButtonStyle(
                                    overlay_color={"":  ft.Colors.TRANSPARENT, "hovered": "#3a1010"},
                                    padding=ft.padding.all(4),
                                ),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(controls=plat_badges, spacing=4) if plat_badges else ft.Container(height=0),
                    ft.Row(
                        controls=[
                            *(
                                [ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=10, color=T.TEXT_MUTED),
                                 ft.Text(product_lbl, size=10, color=T.TEXT_MUTED)]
                                if product_lbl else []
                            ),
                            ft.Container(expand=True),
                            ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, size=10, color=T.TEXT_MUTED),
                            ft.Text(f"{ideas_count} slot{'s' if ideas_count != 1 else ''}",
                                    size=10, color=T.TEXT_MUTED),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=5,
            ),
            bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
            border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_click=_on_click,
            ink=True,
        )

    # ── Right panel — Create ────────────────────────────────────────────────────

    def _build_create_panel(self) -> ft.Column:
        self._c_name_f     = _tf("Campaign Name", "e.g. Summer Sale 2025")
        self._c_start_f    = _tf("Start Date", "YYYY-MM-DD")
        self._c_end_f      = _tf("End Date",   "YYYY-MM-DD")
        self._c_daily_f    = _tf("Daily Budget ($)", "0")
        self._c_total_f    = _tf("Total Budget ($)", "0")
        self._c_audience_f = _tf("Target Audience", "Age, interests, location…", multiline=True, min_lines=2, max_lines=3)
        self._c_notes_f    = _tf("Notes", "Campaign goals and context…", multiline=True, min_lines=2, max_lines=3)
        self._c_strategy   = None
        self._c_platforms  = set()
        self._c_objective  = None
        self._c_strategy_chips = {}
        self._c_platform_chips = {}
        self._c_objective_chips = {}

        strategy_rows = [
            ft.Row(
                controls=[
                    self._c_strategy_chip(k, lbl, icon, desc)
                    for k, lbl, icon, desc in _STRATEGIES[i:i+2]
                ],
                spacing=6,
            )
            for i in range(0, len(_STRATEGIES), 2)
        ]

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=18, color=T.ACCENT_LIGHT),
                            ft.Text("New Campaign", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=20, vertical=16),
                    bgcolor=T.BG_SECONDARY,
                ),
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            _form_label("Campaign Name", ft.Icons.LABEL_OUTLINE),
                            self._c_name_f,
                            ft.Container(height=4),
                            _form_label("Strategy", ft.Icons.LIGHTBULB_OUTLINE),
                            ft.Column(controls=strategy_rows, spacing=6),
                            ft.Container(height=4),
                            _form_label("Platforms", ft.Icons.DEVICES_OUTLINED),
                            ft.Row(
                                controls=[self._c_platform_chip(k, lbl, color) for k, lbl, color in _PLATFORMS],
                                wrap=True, spacing=6, run_spacing=6,
                            ),
                            ft.Container(height=4),
                            _form_label("Objective", ft.Icons.FLAG_OUTLINED),
                            ft.Row(
                                controls=[self._c_objective_chip(k, lbl, icon) for k, lbl, icon in _OBJECTIVES],
                                wrap=True, spacing=6, run_spacing=6,
                            ),
                            ft.Container(height=4),
                            _form_label("Schedule", ft.Icons.DATE_RANGE_OUTLINED),
                            ft.Row(controls=[self._c_start_f, self._c_end_f], spacing=8),
                            ft.Container(height=4),
                            _form_label("Budget", ft.Icons.PAYMENTS_OUTLINED),
                            ft.Row(controls=[self._c_daily_f, self._c_total_f], spacing=8),
                            ft.Container(height=4),
                            _form_label("Target Audience", ft.Icons.PEOPLE_OUTLINE),
                            self._c_audience_f,
                            ft.Container(height=4),
                            _form_label("Notes", ft.Icons.NOTES_OUTLINED),
                            self._c_notes_f,
                            ft.Container(height=14),
                            ft.ElevatedButton(
                                "Create Campaign",
                                icon=ft.Icons.ROCKET_LAUNCH_OUTLINED,
                                on_click=lambda e: self._submit_create(),
                                width=float("inf"),
                                style=ft.ButtonStyle(
                                    bgcolor={"": T.ACCENT, "hovered": T.ACCENT_HOVER},
                                    color="#ffffff",
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                                ),
                            ),
                            ft.Container(height=8),
                        ],
                        spacing=6,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=20, vertical=14),
                ),
            ],
            spacing=0,
            expand=True,
        )

    # Create panel chips
    def _c_strategy_chip(self, key: str, label: str, icon, desc: str) -> ft.Container:
        chip = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[
                        ft.Icon(icon, size=14, color=T.TEXT_SECONDARY),
                        ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=T.TEXT_SECONDARY),
                    ], spacing=5),
                    ft.Text(desc, size=10, color=T.TEXT_MUTED),
                ],
                spacing=3, tight=True,
            ),
            bgcolor=T.BG_CARD, border=ft.border.all(1, T.BORDER),
            border_radius=8, padding=ft.padding.symmetric(horizontal=10, vertical=8),
            expand=True, on_click=lambda e, k=key: self._c_toggle_strategy(k), ink=True,
        )
        self._c_strategy_chips[key] = chip
        return chip

    def _c_platform_chip(self, key: str, label: str, color: str) -> ft.Container:
        chip = ft.Container(
            content=ft.Row(controls=[
                ft.Container(width=8, height=8, bgcolor=color, border_radius=4),
                ft.Text(label, size=11, color=T.TEXT_SECONDARY),
            ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            bgcolor=T.BG_CARD, border=ft.border.all(1, T.BORDER),
            border_radius=20, padding=ft.padding.symmetric(horizontal=10, vertical=5),
            on_click=lambda e, k=key: self._c_toggle_platform(k), ink=True,
        )
        self._c_platform_chips[key] = chip
        return chip

    def _c_objective_chip(self, key: str, label: str, icon) -> ft.Container:
        chip = ft.Container(
            content=ft.Row(controls=[
                ft.Icon(icon, size=12, color=T.TEXT_SECONDARY),
                ft.Text(label, size=11, color=T.TEXT_SECONDARY),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            bgcolor=T.BG_CARD, border=ft.border.all(1, T.BORDER),
            border_radius=20, padding=ft.padding.symmetric(horizontal=10, vertical=5),
            on_click=lambda e, k=key: self._c_toggle_objective(k), ink=True,
        )
        self._c_objective_chips[key] = chip
        return chip

    def _c_toggle_strategy(self, key: str) -> None:
        self._c_strategy = key if key != self._c_strategy else None
        for k, chip in self._c_strategy_chips.items():
            sel = (k == self._c_strategy)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            row = chip.content.controls[0]
            row.controls[0].color = T.ACCENT_LIGHT if sel else T.TEXT_SECONDARY
            row.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
            try: chip.update()
            except Exception: pass

    def _c_toggle_platform(self, key: str) -> None:
        self._c_platforms.discard(key) if key in self._c_platforms else self._c_platforms.add(key)
        chip = self._c_platform_chips[key]
        sel  = key in self._c_platforms
        chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
        chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
        chip.content.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
        try: chip.update()
        except Exception: pass

    def _c_toggle_objective(self, key: str) -> None:
        self._c_objective = key if key != self._c_objective else None
        for k, chip in self._c_objective_chips.items():
            sel = (k == self._c_objective)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            chip.content.controls[0].color = T.ACCENT_LIGHT if sel else T.TEXT_SECONDARY
            chip.content.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
            try: chip.update()
            except Exception: pass

    def _submit_create(self) -> None:
        if not self.state.current_project:
            self._snack("Select a project first.", error=True)
            return
        name = (self._c_name_f.value or "").strip()
        if not name:
            self._c_name_f.error_text = "Name is required"
            self._c_name_f.update()
            return
        self._c_name_f.error_text = None
        if not self._c_platforms:
            self._snack("Select at least one platform.", error=True)
            return

        c = campaign_repo.create_campaign(
            project_id=self.state.current_project.id,
            name=name,
            strategy=self._c_strategy or "",
            objective=self._c_objective or "",
            platforms=json.dumps(sorted(self._c_platforms)),
            daily_budget=_parse_float(self._c_daily_f.value),
            total_budget=_parse_float(self._c_total_f.value),
            start_date=(self._c_start_f.value or "").strip(),
            end_date=(self._c_end_f.value or "").strip(),
            target_audience=(self._c_audience_f.value or "").strip(),
            notes=(self._c_notes_f.value or "").strip(),
        )
        self._campaign_folder(c).mkdir(parents=True, exist_ok=True)
        self._refresh()
        self._snack(f'"{name}" created!')
        self._select_campaign(c)

    # ── Right panel — Detail ────────────────────────────────────────────────────

    def _load_detail(self, c: Campaign) -> None:
        self._idea_entries.clear()
        self._ideas_col.controls.clear()
        for idea in json.loads(c.video_ideas or "[]"):
            entry = self._entry_from_dict(idea)
            self._idea_entries.append(entry)
            self._ideas_col.controls.append(self._build_slot_card(entry))

        self._right.content = self._build_detail_panel(c)
        try:
            self._right.update()
        except Exception:
            pass

    def _build_detail_panel(self, c: Campaign) -> ft.Column:
        # Init all field refs
        self._d_name_f         = _inline_tf(c.name)
        self._d_start_f        = _tf("Start", "YYYY-MM-DD", value=c.start_date)
        self._d_end_f          = _tf("End",   "YYYY-MM-DD", value=c.end_date)
        self._d_daily_f        = _tf("Daily ($)", "0", value=str(c.daily_budget) if c.daily_budget else "")
        self._d_total_f        = _tf("Total ($)", "0", value=str(c.total_budget) if c.total_budget else "")
        self._d_audience_f     = _tf("Target Audience", "Age, interests, location…", value=c.target_audience, multiline=True, min_lines=2, max_lines=4)
        self._d_notes_f        = _tf("Notes", "Campaign goals…", value=c.notes, multiline=True, min_lines=2, max_lines=4)
        self._d_product_name_f = _tf("Product / Service Name", "What are you promoting?", value=c.product_name)
        self._d_product_desc_f = _tf("Key Benefits & Description", "What it does, unique angle…", value=c.product_description, multiline=True, min_lines=4, max_lines=8)
        self._d_strategy  = c.strategy or None
        self._d_platforms = set(json.loads(c.platforms or "[]"))
        self._d_objective = c.objective or None
        self._d_strategy_chips  = {}
        self._d_platform_chips  = {}
        self._d_objective_chips = {}
        self._d_settings_expanded = False
        self._d_tab = "products"
        self._d_tab_btns = {}
        self._d_product_ids = set(json.loads(c.product_ids or "[]"))

        status_opts = [ft.dropdown.Option(s, s.capitalize())
                       for s in ("draft", "active", "paused", "completed")]
        self._d_status_dd = ft.Dropdown(
            value=c.status, options=status_opts,
            bgcolor=T.BG_INPUT, border_color=T.BORDER,
            focused_border_color=T.ACCENT, color=T.TEXT_PRIMARY,
            label_style=ft.TextStyle(color=T.TEXT_MUTED),
            border_radius=8, width=130,
            on_change=lambda e: self._auto_save_campaign(refresh_list=True),
        )
        self._d_name_f.on_blur = lambda e: self._auto_save_campaign(refresh_list=True)

        # Settings accordion
        self._d_settings_expand_icon = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=16, color=T.TEXT_MUTED)
        inner_form = self._build_settings_form()
        self._d_settings_form = ft.Container(
            content=inner_form,
            visible=False,
            padding=ft.padding.symmetric(horizontal=20, vertical=0),
        )
        settings_accordion = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.TUNE, size=13, color=T.TEXT_MUTED),
                                ft.Text("Campaign Settings", size=11, color=T.TEXT_MUTED,
                                        weight=ft.FontWeight.W_500),
                                ft.Container(expand=True),
                                self._d_settings_expand_icon,
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=20, vertical=10),
                        on_click=lambda e: self._toggle_settings(),
                        ink=True,
                    ),
                    self._d_settings_form,
                ],
                spacing=0,
            ),
            bgcolor=T.BG_SECONDARY,
        )

        # Tab bar + content
        tab_bar = self._build_tab_control()
        self._d_tab_content = ft.Container(
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
        )
        self._switch_tab("products", force=True)

        def _back(e):   self._deselect()
        def _delete(e): self._confirm_delete(c)

        return ft.Column(
            controls=[
                self._build_detail_header(c, _back, _delete),
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._build_meta_strip(c),
                            T.divider(),
                            settings_accordion,
                            T.divider(),
                            tab_bar,
                            T.divider(),
                            self._d_tab_content,
                        ],
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _build_detail_header(self, c: Campaign, back_fn, delete_fn) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        tooltip="All campaigns",
                        icon_color=T.TEXT_MUTED, icon_size=18,
                        on_click=back_fn,
                        style=ft.ButtonStyle(
                            overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                        ),
                    ),
                    self._d_name_f,
                    self._d_status_dd,
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Delete campaign",
                        icon_color=T.ERROR, icon_size=18,
                        on_click=delete_fn,
                        style=ft.ButtonStyle(
                            overlay_color={"": ft.Colors.TRANSPARENT, "hovered": "#3a1010"},
                        ),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            bgcolor=T.BG_SECONDARY,
        )

    def _build_meta_strip(self, c: Campaign) -> ft.Container:
        platforms = json.loads(c.platforms or "[]")
        plat_badges = [
            ft.Container(
                content=ft.Text(_PLATFORM_LABELS.get(p, p), size=9,
                                weight=ft.FontWeight.BOLD, color="#fff"),
                bgcolor=_PLATFORM_COLORS.get(p, T.ACCENT),
                border_radius=4,
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
            )
            for p in platforms
        ]

        controls: list[ft.Control] = [*plat_badges]

        strategy_lbl = _STRATEGY_LABELS.get(c.strategy, "")
        if strategy_lbl:
            controls += [
                ft.Text("·", size=11, color=T.TEXT_MUTED),
                ft.Container(
                    content=ft.Text(strategy_lbl, size=10, color=T.ACCENT_LIGHT,
                                    weight=ft.FontWeight.W_600),
                    bgcolor=T.ACCENT_DIM, border_radius=4,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                ),
            ]

        if c.start_date or c.end_date:
            date_str = f"{c.start_date or '?'}  →  {c.end_date or '?'}"
            controls += [
                ft.Text("·", size=11, color=T.TEXT_MUTED),
                ft.Icon(ft.Icons.DATE_RANGE_OUTLINED, size=11, color=T.TEXT_MUTED),
                ft.Text(date_str, size=11, color=T.TEXT_SECONDARY),
            ]

        if c.daily_budget:
            controls += [
                ft.Text("·", size=11, color=T.TEXT_MUTED),
                ft.Icon(ft.Icons.PAYMENTS_OUTLINED, size=11, color=T.TEXT_MUTED),
                ft.Text(f"${c.daily_budget:.0f}/day", size=11, color=T.TEXT_SECONDARY),
            ]

        return ft.Container(
            content=ft.Row(
                controls=controls,
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
        )

    def _build_settings_form(self) -> ft.Column:
        _auto = lambda e: self._auto_save_campaign()  # noqa: E731
        for f in (self._d_start_f, self._d_end_f, self._d_daily_f,
                  self._d_total_f, self._d_audience_f, self._d_notes_f):
            if f:
                f.on_blur = _auto
        strategy_rows = [
            ft.Row(
                controls=[self._d_strategy_chip(k, lbl, icon, desc)
                           for k, lbl, icon, desc in _STRATEGIES[i:i+2]],
                spacing=6,
            )
            for i in range(0, len(_STRATEGIES), 2)
        ]
        return ft.Column(
            controls=[
                ft.Container(height=6),
                _form_label("Strategy", ft.Icons.LIGHTBULB_OUTLINE),
                ft.Column(controls=strategy_rows, spacing=6),
                ft.Container(height=4),
                _form_label("Platforms", ft.Icons.DEVICES_OUTLINED),
                ft.Row(
                    controls=[self._d_platform_chip(k, lbl, color) for k, lbl, color in _PLATFORMS],
                    wrap=True, spacing=6, run_spacing=6,
                ),
                ft.Container(height=4),
                _form_label("Objective", ft.Icons.FLAG_OUTLINED),
                ft.Row(
                    controls=[self._d_objective_chip(k, lbl, icon) for k, lbl, icon in _OBJECTIVES],
                    wrap=True, spacing=6, run_spacing=6,
                ),
                ft.Container(height=4),
                _form_label("Schedule", ft.Icons.DATE_RANGE_OUTLINED),
                ft.Row(controls=[self._d_start_f, self._d_end_f], spacing=8),
                ft.Container(height=4),
                _form_label("Budget", ft.Icons.PAYMENTS_OUTLINED),
                ft.Row(controls=[self._d_daily_f, self._d_total_f], spacing=8),
                ft.Container(height=4),
                _form_label("Target Audience", ft.Icons.PEOPLE_OUTLINE),
                self._d_audience_f,
                ft.Container(height=4),
                _form_label("Notes", ft.Icons.NOTES_OUTLINED),
                self._d_notes_f,
                ft.Container(height=12),
            ],
            spacing=6,
        )

    def _toggle_settings(self) -> None:
        self._d_settings_expanded = not self._d_settings_expanded
        if self._d_settings_form:
            self._d_settings_form.visible = self._d_settings_expanded
            try: self._d_settings_form.update()
            except Exception: pass
        if self._d_settings_expand_icon:
            self._d_settings_expand_icon.name = (
                ft.Icons.KEYBOARD_ARROW_UP if self._d_settings_expanded
                else ft.Icons.KEYBOARD_ARROW_DOWN
            )
            try: self._d_settings_expand_icon.update()
            except Exception: pass

    def _build_tab_control(self) -> ft.Container:
        def _make_tab(key: str, label: str, icon) -> ft.Container:
            is_active = (key == self._d_tab)
            btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=14,
                                color=T.ACCENT_LIGHT if is_active else T.TEXT_MUTED),
                        ft.Text(label, size=12,
                                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
                                color=T.TEXT_PRIMARY if is_active else T.TEXT_MUTED),
                    ],
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=T.ACCENT_DIM if is_active else ft.Colors.TRANSPARENT,
                border=ft.border.all(1, T.ACCENT_LIGHT if is_active else ft.Colors.TRANSPARENT),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
                on_click=lambda e, k=key: self._switch_tab(k),
                ink=True,
            )
            self._d_tab_btns[key] = btn
            return btn

        return ft.Container(
            content=ft.Row(
                controls=[
                    _make_tab("products", "Product",     ft.Icons.INVENTORY_2_OUTLINED),
                    _make_tab("schedule", "Ad Schedule", ft.Icons.VIDEO_LIBRARY_OUTLINED),
                    _make_tab("calendar", "Calendar",    ft.Icons.CALENDAR_MONTH_OUTLINED),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
        )

    def _switch_tab(self, tab: str, force: bool = False) -> None:
        if tab == self._d_tab and not force:
            return
        self._d_tab = tab

        for k, btn in self._d_tab_btns.items():
            is_active = (k == tab)
            btn.bgcolor = T.ACCENT_DIM if is_active else ft.Colors.TRANSPARENT
            btn.border  = ft.border.all(1, T.ACCENT_LIGHT if is_active else ft.Colors.TRANSPARENT)
            row = btn.content
            row.controls[0].color  = T.ACCENT_LIGHT if is_active else T.TEXT_MUTED
            row.controls[1].color  = T.TEXT_PRIMARY if is_active else T.TEXT_MUTED
            row.controls[1].weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL

        if self._d_tab_content is None:
            return

        self._d_tab_content.content = (
            self._build_products_content()      if tab == "products"
            else self._build_calendar_content() if tab == "calendar"
            else self._build_schedule_content()
        )
        try: self.page.update()
        except Exception: pass

    def _build_products_content(self) -> ft.Column:
        if not self.state.current_project:
            return ft.Column(controls=[
                ft.Text("No project selected.", color=T.TEXT_MUTED, size=12)
            ])

        products = product_repo.get_products(self.state.current_project.id)
        total    = len(products)
        included = sum(1 for p in products if p.id in self._d_product_ids)

        add_btn = ft.ElevatedButton(
            "Add Product",
            icon=ft.Icons.ADD,
            on_click=lambda e: self._open_add_product_dialog(),
            style=ft.ButtonStyle(
                bgcolor={"": T.BG_CARD, "hovered": T.ACCENT_DIM},
                color=T.TEXT_PRIMARY,
                side=ft.BorderSide(1, T.BORDER),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
        )

        subtitle = (
            f"{total} product{'s' if total != 1 else ''} in project"
            + (f"  ·  {included} promoted in this campaign" if total else "")
        )

        header = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Product Catalog", size=13,
                                weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ft.Text(subtitle, size=10, color=T.TEXT_MUTED),
                    ],
                    spacing=2, tight=True, expand=True,
                ),
                add_btn,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        if not products:
            body: list[ft.Control] = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=40, color=T.TEXT_MUTED),
                            ft.Text("No products yet", size=13, color=T.TEXT_SECONDARY,
                                    weight=ft.FontWeight.W_500),
                            ft.Text("Add products to your project and mark which ones\n"
                                    "this campaign promotes.",
                                    size=11, color=T.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.padding.symmetric(vertical=40),
                    alignment=ft.alignment.center,
                )
            ]
        else:
            body = [self._build_product_card(p) for p in products]

        return ft.Column(
            controls=[header, ft.Container(height=4), *body, ft.Container(height=40)],
            spacing=8,
        )

    def _build_product_card(self, product: Product) -> ft.Container:
        is_included = product.id in self._d_product_ids

        check_icon = ft.Icon(
            ft.Icons.CHECK_BOX if is_included else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
            size=18,
            color=T.ACCENT_LIGHT if is_included else T.TEXT_MUTED,
        )
        check_box = ft.Container(
            content=check_icon,
            bgcolor=T.ACCENT_DIM if is_included else T.BG_CARD,
            border=ft.border.all(1, T.ACCENT_LIGHT if is_included else T.BORDER),
            border_radius=6,
            width=32, height=32,
            alignment=ft.alignment.center,
            tooltip="Toggle promotion in this campaign",
            ink=True,
        )
        card = ft.Container()  # forward ref for border update

        def _toggle(e):
            if product.id in self._d_product_ids:
                self._d_product_ids.discard(product.id)
                active = False
            else:
                self._d_product_ids.add(product.id)
                active = True
            check_icon.name  = ft.Icons.CHECK_BOX if active else ft.Icons.CHECK_BOX_OUTLINE_BLANK
            check_icon.color = T.ACCENT_LIGHT if active else T.TEXT_MUTED
            check_box.bgcolor = T.ACCENT_DIM if active else T.BG_CARD
            check_box.border  = ft.border.all(1, T.ACCENT_LIGHT if active else T.BORDER)
            card.bgcolor = T.ACCENT_DIM if active else T.BG_CARD
            card.border  = ft.border.all(1, T.ACCENT_LIGHT if active else T.BORDER)
            try:
                check_icon.update()
                check_box.update()
                card.update()
            except Exception:
                pass
            self._persist_product_ids()

        check_box.on_click = _toggle

        price_badge = (
            ft.Container(
                content=ft.Text(product.price, size=10, color=T.SUCCESS,
                                weight=ft.FontWeight.W_600),
                bgcolor="#0a2010",
                border=ft.border.all(1, T.SUCCESS),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=7, vertical=2),
            )
            if product.price else ft.Container()
        )

        desc_text = (
            ft.Text(product.description, size=11, color=T.TEXT_SECONDARY,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
            if product.description else ft.Container()
        )

        url_row = (
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LINK, size=10, color=T.TEXT_MUTED),
                    ft.Text(
                        (product.url[:55] + "…" if len(product.url) > 55 else product.url),
                        size=10, color=T.TEXT_MUTED,
                    ),
                ],
                spacing=3,
            )
            if product.url else ft.Container()
        )

        def _edit(e):   self._open_edit_product_dialog(product)
        def _delete(e): self._confirm_delete_product(product)

        info_col = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(product.name, size=13, weight=ft.FontWeight.W_600,
                                color=T.TEXT_PRIMARY, expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        price_badge,
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED, icon_size=15,
                            icon_color=T.TEXT_MUTED, tooltip="Edit product",
                            on_click=_edit,
                            style=ft.ButtonStyle(
                                overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                padding=4,
                            ),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE, icon_size=15,
                            icon_color=T.ERROR, tooltip="Delete product",
                            on_click=_delete,
                            style=ft.ButtonStyle(
                                overlay_color={"": ft.Colors.TRANSPARENT, "hovered": "#3a1010"},
                                padding=4,
                            ),
                        ),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                desc_text,
                url_row,
            ],
            spacing=3,
            tight=True,
            expand=True,
        )

        card.content = ft.Row(
            controls=[check_box, info_col],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        card.bgcolor      = T.ACCENT_DIM if is_included else T.BG_CARD
        card.border       = ft.border.all(1, T.ACCENT_LIGHT if is_included else T.BORDER)
        card.border_radius = 10
        card.padding      = ft.padding.symmetric(horizontal=14, vertical=12)
        return card

    def _reload_products_tab(self) -> None:
        if self._d_tab_content is None or self._d_tab != "products":
            return
        self._d_tab_content.content = self._build_products_content()
        try:
            self._d_tab_content.update()
        except Exception:
            pass

    def _open_add_product_dialog(self) -> None:
        name_f  = _tf("Product Name",    "e.g. Nike Air Max")
        price_f = _tf("Price",           "e.g. $29.99")
        desc_f  = _tf("Description",     "Key benefits, features…",
                      multiline=True, min_lines=2, max_lines=4)
        url_f   = _tf("Product URL",     "https://…")

        def _save(e):
            name = (name_f.value or "").strip()
            if not name:
                name_f.error_text = "Name is required"
                name_f.update()
                return
            if not self.state.current_project:
                return
            product_repo.create_product(
                project_id=self.state.current_project.id,
                name=name,
                description=(desc_f.value or "").strip(),
                price=(price_f.value or "").strip(),
                url=(url_f.value or "").strip(),
            )
            dlg.open = False
            self.page.update()
            self._reload_products_tab()

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Product", color=T.TEXT_PRIMARY,
                          size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[name_f, price_f, desc_f, url_f],
                spacing=10, tight=True, width=420,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Add Product", on_click=_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _open_edit_product_dialog(self, product: Product) -> None:
        name_f  = _tf("Product Name", "", value=product.name)
        price_f = _tf("Price",        "e.g. $29.99", value=product.price)
        desc_f  = _tf("Description",  "", value=product.description,
                      multiline=True, min_lines=2, max_lines=4)
        url_f   = _tf("Product URL",  "https://…", value=product.url)

        def _save(e):
            name = (name_f.value or "").strip()
            if not name:
                name_f.error_text = "Name is required"
                name_f.update()
                return
            product.name        = name
            product.description = (desc_f.value or "").strip()
            product.price       = (price_f.value or "").strip()
            product.url         = (url_f.value or "").strip()
            product_repo.update_product(product)
            dlg.open = False
            self.page.update()
            self._reload_products_tab()

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Product", color=T.TEXT_PRIMARY,
                          size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[name_f, price_f, desc_f, url_f],
                spacing=10, tight=True, width=420,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Save", on_click=_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _confirm_delete_product(self, product: Product) -> None:
        def _do_delete(e):
            self._d_product_ids.discard(product.id)
            product_repo.delete_product(product.id)
            dlg.open = False
            self.page.update()
            self._reload_products_tab()

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Product?", color=T.ERROR,
                          size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Text(
                f'"{product.name}" will be permanently removed from the project.',
                color=T.TEXT_SECONDARY, size=13,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                ft.ElevatedButton("Delete", on_click=_do_delete, style=ft.ButtonStyle(
                    bgcolor={"": T.ERROR, "hovered": "#cc0000"}, color="#ffffff",
                    shape=ft.RoundedRectangleBorder(radius=8),
                )),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _build_ai_model_dropdown(self) -> ft.Dropdown:
        loading_opt = ft.dropdown.Option(key="__loading__", text="Loading models…")
        dd = ft.Dropdown(
            value="__loading__",
            options=[loading_opt],
            on_change=self._on_model_dd_change,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            label="AI Model",
            label_style=ft.TextStyle(color=T.TEXT_MUTED),
            border_radius=8,
            expand=True,
            text_size=11,
        )
        self._gen_model_dd = dd
        threading.Thread(target=self._populate_model_dropdown, args=(dd,), daemon=True).start()
        return dd

    def _on_model_dd_change(self, e) -> None:
        val = e.control.value or ""
        if ":" in val:
            self._gen_selected_provider, self._gen_selected_model = val.split(":", 1)

    def _populate_model_dropdown(self, dd: ft.Dropdown) -> None:
        options: list[ft.dropdown.Option] = []

        if is_ollama_running():
            installed = list_installed_models()
            for m in installed:
                name = m.get("name", "")
                if name:
                    options.append(ft.dropdown.Option(
                        key=f"ollama:{name}",
                        text=f"[Local] {name}",
                    ))
        else:
            options.append(ft.dropdown.Option(
                key="ollama:__none__",
                text="[Local] Ollama not running",
            ))

        _labels = {"openai": "OpenAI", "claude": "Claude", "gemini": "Gemini"}
        for pname in ["openai", "claude", "gemini"]:
            try:
                prov = get_provider(pname)
                if prov.is_configured():
                    models = prov.list_models()
                    for mdl in models[:10]:
                        options.append(ft.dropdown.Option(
                            key=f"{pname}:{mdl}",
                            text=f"[{_labels[pname]}] {mdl}",
                        ))
            except Exception:
                pass

        if not options:
            options.append(ft.dropdown.Option(
                key="ollama:__none__",
                text="No AI available — start Ollama or add API key",
            ))

        default_key = options[0].key
        if ":" in default_key:
            self._gen_selected_provider, self._gen_selected_model = default_key.split(":", 1)

        dd.options = options
        dd.value   = default_key
        try:
            dd.update()
        except Exception:
            pass

    def _build_schedule_content(self) -> ft.Column:
        self._gen_status = ft.Text("", size=11, color=T.SUCCESS, visible=False)
        self._gen_btn = ft.ElevatedButton(
            "Generate Ideas",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=self._generate_ideas,
            style=ft.ButtonStyle(
                bgcolor={"": T.BG_CARD, "hovered": T.ACCENT_DIM},
                color=T.ACCENT_LIGHT,
                side=ft.BorderSide(1, T.ACCENT),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
        )
        self._gen_stop_btn = ft.ElevatedButton(
            "Stop",
            icon=ft.Icons.STOP_CIRCLE_OUTLINED,
            visible=False,
            on_click=lambda e: self._stop_generation(),
            style=ft.ButtonStyle(
                bgcolor={"": T.BG_CARD, "hovered": "#3a1010"},
                color=T.ERROR,
                side=ft.BorderSide(1, T.ERROR),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
        )
        model_dd = self._build_ai_model_dropdown()

        slot_count   = len(self._idea_entries)
        posted       = sum(1 for e in self._idea_entries if e.get("pub_status") == "posted")
        in_progress  = sum(1 for e in self._idea_entries if e.get("pub_status") == "in_progress")

        stats_row = ft.Row(
            controls=[
                _mini_stat(str(slot_count),  "Total",       T.BORDER_ACCENT),
                _mini_stat(str(in_progress), "In Progress", T.WARNING),
                _mini_stat(str(posted),      "Posted",      T.SUCCESS),
            ],
            spacing=8,
        ) if slot_count else ft.Container()

        add_btn = ft.ElevatedButton(
            "Add Slot",
            icon=ft.Icons.ADD,
            on_click=lambda e: self._add_slot(),
            style=ft.ButtonStyle(
                bgcolor={"": T.BG_CARD, "hovered": T.ACCENT_DIM},
                color=T.TEXT_PRIMARY,
                side=ft.BorderSide(1, T.BORDER),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
        )

        header = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Ad Schedule", size=13,
                                weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ft.Text("Plan and schedule your video ad slots",
                                size=10, color=T.TEXT_MUTED),
                    ],
                    spacing=2, tight=True, expand=True,
                ),
                add_btn,
                self._gen_btn,
                self._gen_stop_btn,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        model_row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=14, color=T.TEXT_MUTED),
                model_dd,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        empty = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, size=40, color=T.TEXT_MUTED),
                    ft.Text("No ad slots yet", size=13, color=T.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_500),
                    ft.Text("Add a slot or generate ideas with AI",
                            size=11, color=T.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.alignment.center,
            visible=(slot_count == 0),
        )

        gen_config = self._build_gen_config_row()

        return ft.Column(
            controls=[
                header,
                model_row,
                gen_config,
                ft.Container(content=self._gen_status, padding=ft.padding.only(left=2)),
                stats_row,
                ft.Container(height=4),
                empty,
                self._ideas_col,
                ft.Container(height=40),
            ],
            spacing=8,
        )

    # ── Generation config row ───────────────────────────────────────────────────

    def _build_gen_config_row(self) -> ft.Container:
        self._gen_vpd_chips = {}
        self._gen_dur_chips = {}
        self._gen_type_chips = {}

        def _vpd_chip(v: int) -> ft.Container:
            is_sel = (v == self._gen_videos_per_day)
            chip = ft.Container(
                content=ft.Text(str(v), size=10, weight=ft.FontWeight.W_600,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_MUTED),
                bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
                border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=11, vertical=4),
                on_click=lambda e, val=v: self._set_vpd(val),
                ink=True,
            )
            self._gen_vpd_chips[v] = chip
            return chip

        _dur_options = [(7, "1 wk"), (14, "2 wks"), (21, "3 wks"), (30, "30 d")]

        def _dur_chip(days: int, label: str) -> ft.Container:
            is_sel = (days == self._gen_duration_days)
            chip = ft.Container(
                content=ft.Text(label, size=10, weight=ft.FontWeight.W_600,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_MUTED),
                bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
                border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                on_click=lambda e, d=days: self._set_dur(d),
                ink=True,
            )
            self._gen_dur_chips[days] = chip
            return chip

        count = self._gen_videos_per_day * self._gen_duration_days
        self._gen_count_badge = ft.Text(
            f"→ {count} ideas",
            size=11, weight=ft.FontWeight.BOLD, color=T.ACCENT_LIGHT,
        )

        _content_types = [
            ("mixed", "Video + Image", ft.Icons.PERM_MEDIA_OUTLINED),
            ("video", "Video only",    ft.Icons.VIDEOCAM_OUTLINED),
            ("image", "Image only",    ft.Icons.IMAGE_OUTLINED),
        ]

        def _type_chip(key: str, label: str, icon) -> ft.Container:
            is_sel = (key == self._gen_content_type)
            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=11,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_MUTED),
                        ft.Text(label, size=10, weight=ft.FontWeight.W_600,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_MUTED),
                    ],
                    spacing=4,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
                border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                on_click=lambda e, k=key: self._set_content_type(k),
                ink=True,
            )
            self._gen_type_chips[key] = chip
            return chip

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Ideas/day", size=9, color=T.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600,
                                    style=ft.TextStyle(letter_spacing=0.8)),
                            *[_vpd_chip(v) for v in [1, 2, 3, 5]],
                            ft.Container(width=6),
                            ft.Container(width=1, height=16, bgcolor=T.BORDER),
                            ft.Container(width=6),
                            ft.Text("Duration", size=9, color=T.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600,
                                    style=ft.TextStyle(letter_spacing=0.8)),
                            *[_dur_chip(d, lbl) for d, lbl in _dur_options],
                            ft.Container(expand=True),
                            self._gen_count_badge,
                        ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Content type", size=9, color=T.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600,
                                    style=ft.TextStyle(letter_spacing=0.8)),
                            *[_type_chip(k, lbl, ico) for k, lbl, ico in _content_types],
                        ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=T.BG_SECONDARY,
            border=ft.border.all(1, T.BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )

    def _set_vpd(self, v: int) -> None:
        self._gen_videos_per_day = v
        self._update_gen_chips()

    def _set_dur(self, days: int) -> None:
        self._gen_duration_days = days
        self._update_gen_chips()

    def _update_gen_chips(self) -> None:
        for v, chip in self._gen_vpd_chips.items():
            sel = (v == self._gen_videos_per_day)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            chip.content.color = T.ACCENT_LIGHT if sel else T.TEXT_MUTED
            try: chip.update()
            except Exception: pass
        for d, chip in self._gen_dur_chips.items():
            sel = (d == self._gen_duration_days)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            chip.content.color = T.ACCENT_LIGHT if sel else T.TEXT_MUTED
            try: chip.update()
            except Exception: pass
        count = self._gen_videos_per_day * self._gen_duration_days
        if self._gen_count_badge:
            self._gen_count_badge.value = f"→ {count} ideas"
            try: self._gen_count_badge.update()
            except Exception: pass

    def _set_content_type(self, key: str) -> None:
        self._gen_content_type = key
        for k, chip in self._gen_type_chips.items():
            sel = (k == key)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            row = chip.content
            row.controls[0].color = T.ACCENT_LIGHT if sel else T.TEXT_MUTED
            row.controls[1].color = T.ACCENT_LIGHT if sel else T.TEXT_MUTED
            try: chip.update()
            except Exception: pass

    # Detail chips (for the settings accordion)
    def _d_strategy_chip(self, key: str, label: str, icon, desc: str) -> ft.Container:
        is_sel = (key == self._d_strategy)
        chip = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[
                        ft.Icon(icon, size=14, color=T.ACCENT_LIGHT if is_sel else T.TEXT_SECONDARY),
                        ft.Text(label, size=12, weight=ft.FontWeight.W_600,
                                color=T.TEXT_PRIMARY if is_sel else T.TEXT_SECONDARY),
                    ], spacing=5),
                    ft.Text(desc, size=10, color=T.TEXT_MUTED),
                ],
                spacing=3, tight=True,
            ),
            bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
            border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
            border_radius=8, padding=ft.padding.symmetric(horizontal=10, vertical=8),
            expand=True, on_click=lambda e, k=key: self._d_toggle_strategy(k), ink=True,
        )
        self._d_strategy_chips[key] = chip
        return chip

    def _d_platform_chip(self, key: str, label: str, color: str) -> ft.Container:
        is_sel = key in self._d_platforms
        chip = ft.Container(
            content=ft.Row(controls=[
                ft.Container(width=8, height=8, bgcolor=color, border_radius=4),
                ft.Text(label, size=11, color=T.TEXT_PRIMARY if is_sel else T.TEXT_SECONDARY),
            ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
            border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
            border_radius=20, padding=ft.padding.symmetric(horizontal=10, vertical=5),
            on_click=lambda e, k=key: self._d_toggle_platform(k), ink=True,
        )
        self._d_platform_chips[key] = chip
        return chip

    def _d_objective_chip(self, key: str, label: str, icon) -> ft.Container:
        is_sel = (key == self._d_objective)
        chip = ft.Container(
            content=ft.Row(controls=[
                ft.Icon(icon, size=12, color=T.ACCENT_LIGHT if is_sel else T.TEXT_SECONDARY),
                ft.Text(label, size=11, color=T.TEXT_PRIMARY if is_sel else T.TEXT_SECONDARY),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
            border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
            border_radius=20, padding=ft.padding.symmetric(horizontal=10, vertical=5),
            on_click=lambda e, k=key: self._d_toggle_objective(k), ink=True,
        )
        self._d_objective_chips[key] = chip
        return chip

    def _d_toggle_strategy(self, key: str) -> None:
        self._d_strategy = key if key != self._d_strategy else None
        for k, chip in self._d_strategy_chips.items():
            sel = (k == self._d_strategy)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            row = chip.content.controls[0]
            row.controls[0].color = T.ACCENT_LIGHT if sel else T.TEXT_SECONDARY
            row.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
            try: chip.update()
            except Exception: pass
        self._auto_save_campaign()

    def _d_toggle_platform(self, key: str) -> None:
        self._d_platforms.discard(key) if key in self._d_platforms else self._d_platforms.add(key)
        chip = self._d_platform_chips[key]
        sel  = key in self._d_platforms
        chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
        chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
        chip.content.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
        try: chip.update()
        except Exception: pass
        self._auto_save_campaign()

    def _d_toggle_objective(self, key: str) -> None:
        self._d_objective = key if key != self._d_objective else None
        for k, chip in self._d_objective_chips.items():
            sel = (k == self._d_objective)
            chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
            chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
            chip.content.controls[0].color = T.ACCENT_LIGHT if sel else T.TEXT_SECONDARY
            chip.content.controls[1].color = T.TEXT_PRIMARY if sel else T.TEXT_SECONDARY
            try: chip.update()
            except Exception: pass
        self._auto_save_campaign()

    def _auto_save_campaign(self, *, refresh_list: bool = False) -> None:
        """Persist all campaign fields silently. Called automatically on any field change."""
        c = self._selected
        if c is None:
            return
        name = (self._d_name_f.value or "").strip() if self._d_name_f else c.name
        if not name:
            return

        def _str(ent: dict, key: str, field_key: str) -> str:
            val = ent.get(key, "")
            if not val and field_key in ent and ent[field_key]:
                val = ent[field_key].value or ""
            return val.strip()

        video_ideas_data = [
            {
                "id":            ent["id"],
                "idea_type":     ent.get("idea_type", "video"),
                "title":         _str(ent, "title",          "title_f"),
                "concept":       _str(ent, "concept",         "concept_f"),
                "how_to_film":   _str(ent, "how_to_film",     "film_f"),
                "how_to_cut":    _str(ent, "how_to_cut",      "cut_f"),
                "image_prompt":  _str(ent, "image_prompt",    "image_prompt_f"),
                "scheduled_date":_str(ent, "scheduled_date",  "sched_f"),
                "format":        ent.get("format",     "reel"),
                "pub_status":    ent.get("pub_status",  "in_progress"),
            }
            for ent in self._idea_entries
        ]

        c.name                = name
        c.strategy            = self._d_strategy or ""
        c.objective           = self._d_objective or ""
        c.platforms           = json.dumps(sorted(self._d_platforms))
        c.status              = (self._d_status_dd.value or "draft") if self._d_status_dd else c.status
        c.daily_budget        = _parse_float(self._d_daily_f.value   if self._d_daily_f  else "")
        c.total_budget        = _parse_float(self._d_total_f.value   if self._d_total_f  else "")
        c.start_date          = (self._d_start_f.value    or "").strip() if self._d_start_f    else ""
        c.end_date            = (self._d_end_f.value      or "").strip() if self._d_end_f      else ""
        c.target_audience     = (self._d_audience_f.value or "").strip() if self._d_audience_f else ""
        c.notes               = (self._d_notes_f.value    or "").strip() if self._d_notes_f    else ""
        c.product_name        = (self._d_product_name_f.value or "").strip() if self._d_product_name_f else ""
        c.product_description = (self._d_product_desc_f.value or "").strip() if self._d_product_desc_f else ""
        c.video_ideas         = json.dumps(video_ideas_data)
        c.product_ids         = json.dumps(sorted(self._d_product_ids))

        try:
            campaign_repo.update_campaign(c)
            self._ensure_idea_folders(c, video_ideas_data)
        except Exception:
            pass
        if refresh_list:
            self._refresh()

    # ── Ad slot management ──────────────────────────────────────────────────────

    def _entry_from_dict(self, idea: dict) -> dict:
        idea_type = idea.get("idea_type", "video")
        entry: dict = {
            "id":             idea.get("id") or str(uuid4()),
            "idea_type":      idea_type,
            # Plain-string backing store — always up-to-date via on_change handlers
            "title":          idea.get("title", ""),
            "concept":        idea.get("concept", ""),
            "how_to_film":    idea.get("how_to_film", ""),
            "how_to_cut":     idea.get("how_to_cut", ""),
            "image_prompt":   idea.get("image_prompt", ""),
            "scheduled_date": idea.get("scheduled_date", ""),
            "format":         idea.get("format",    "reel" if idea_type == "video" else "feed"),
            "pub_status":     _migrate_pub_status(idea.get("pub_status", "in_progress")),
            "format_chips":   {},
            "status_chips":   {},
            "card":           None,
        }

        def _mk_on_change(key: str):
            def _handler(e):
                entry[key] = e.control.value or ""
            return _handler

        is_image = (idea_type == "image")
        film_label = "Scenes / Composition" if is_image else "How to Film"
        film_hint  = "Describe each slide or scene…" if is_image else "Camera, location, props, lighting…"
        cut_label  = "Visual Style" if is_image else "How to Cut"
        cut_hint   = "Color palette, text overlays, transitions…" if is_image else "Editing, pacing, music, captions…"

        title_f   = _tf("Title", "Short catchy title", value=entry["title"])
        concept_f = _tf("Concept / Hook", "What's the hook and message?",
                        value=entry["concept"], multiline=True, min_lines=2, max_lines=5)
        film_f    = _tf(film_label, film_hint,
                        value=entry["how_to_film"], multiline=True, min_lines=2, max_lines=4)
        cut_f     = _tf(cut_label, cut_hint,
                        value=entry["how_to_cut"], multiline=True, min_lines=2, max_lines=4)
        image_prompt_f = _tf(
            "Image Generation Prompt",
            "add reference image of the product and prompt: …",
            value=entry["image_prompt"],
            multiline=True, min_lines=2, max_lines=4,
        )
        sched_f   = _tf("Publish Date", "YYYY-MM-DD", value=entry["scheduled_date"])

        title_f.on_change         = _mk_on_change("title")
        concept_f.on_change       = _mk_on_change("concept")
        film_f.on_change          = _mk_on_change("how_to_film")
        cut_f.on_change           = _mk_on_change("how_to_cut")
        image_prompt_f.on_change  = _mk_on_change("image_prompt")
        sched_f.on_change         = _mk_on_change("scheduled_date")

        _save_ideas = lambda e: self._persist_ideas()  # noqa: E731
        title_f.on_blur          = _save_ideas
        concept_f.on_blur        = _save_ideas
        film_f.on_blur           = _save_ideas
        cut_f.on_blur            = _save_ideas
        image_prompt_f.on_blur   = _save_ideas
        sched_f.on_blur          = _save_ideas

        entry["title_f"]         = title_f
        entry["concept_f"]       = concept_f
        entry["film_f"]          = film_f
        entry["cut_f"]           = cut_f
        entry["image_prompt_f"]  = image_prompt_f
        entry["sched_f"]         = sched_f
        return entry

    def _build_slot_card(self, entry: dict) -> ft.Container:
        is_image = (entry.get("idea_type") == "image")

        # ── Format chips ────────────────────────────────────────────────────────
        entry["format_chips"] = {}

        def _toggle_format(key: str) -> None:
            entry["format"] = key
            for k, chip in entry["format_chips"].items():
                sel = (k == key)
                chip.bgcolor = T.ACCENT_DIM if sel else T.BG_CARD
                chip.border  = ft.border.all(1, T.ACCENT_LIGHT if sel else T.BORDER)
                chip.content.color = T.ACCENT_LIGHT if sel else T.TEXT_MUTED
                try: chip.update()
                except Exception: pass

        _image_formats = [("feed", "Feed"), ("story", "Story")]
        _fmt_list = _image_formats if is_image else _AD_FORMATS

        fmt_chips = []
        for fmt_key, fmt_label in _fmt_list:
            is_sel = (entry.get("format") == fmt_key)
            chip = ft.Container(
                content=ft.Text(fmt_label, size=9, weight=ft.FontWeight.W_600,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_MUTED),
                bgcolor=T.ACCENT_DIM if is_sel else T.BG_CARD,
                border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else T.BORDER),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                on_click=lambda e, k=fmt_key: _toggle_format(k),
                ink=True,
            )
            entry["format_chips"][fmt_key] = chip
            fmt_chips.append(chip)

        # ── Status chips ────────────────────────────────────────────────────────
        entry["status_chips"] = {}

        def _toggle_status(key: str) -> None:
            entry["pub_status"] = key
            for sk, sl, stc, sbc, sbc2 in _PUB_STATUSES:
                chip = entry["status_chips"].get(sk)
                if chip is None:
                    continue
                sel = (sk == key)
                chip.bgcolor = sbc if sel else T.BG_CARD
                chip.border  = ft.border.all(1, sbc2 if sel else T.BORDER)
                chip.content.color = stc if sel else T.TEXT_MUTED
                try: chip.update()
                except Exception: pass

        status_chips = []
        for sk, sl, stc, sbc, sbc2 in _PUB_STATUSES:
            is_sel = (entry.get("pub_status") == sk)
            chip = ft.Container(
                content=ft.Text(sl, size=9, weight=ft.FontWeight.W_600,
                                color=stc if is_sel else T.TEXT_MUTED),
                bgcolor=sbc if is_sel else T.BG_CARD,
                border=ft.border.all(1, sbc2 if is_sel else T.BORDER),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                on_click=lambda e, k=sk: _toggle_status(k),
                ink=True,
            )
            entry["status_chips"][sk] = chip
            status_chips.append(chip)

        def _remove(e, ent=entry):
            self._remove_idea(ent)

        def _open_folder(e, ent=entry):
            self._open_idea_folder(ent)

        def _open_detail(e, ent=entry):
            self._open_video_detail_dialog(ent)

        def _pick_date(e, ent=entry):
            self._open_date_picker_dialog(ent)

        type_icon   = ft.Icons.IMAGE_OUTLINED     if is_image else ft.Icons.VIDEOCAM_OUTLINED
        type_color  = T.INFO                      if is_image else T.ACCENT_LIGHT
        type_badge  = ft.Container(
            content=ft.Text("SLIDESHOW" if is_image else "VIDEO",
                            size=9, weight=ft.FontWeight.BOLD, color=type_color),
            bgcolor=T.BG_SECONDARY,
            border=ft.border.all(1, type_color),
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=5, vertical=2),
        )

        film_label_str = "Scenes / Composition" if is_image else "Video Angles / How to Film"
        film_icon      = ft.Icons.PHOTO_LIBRARY_OUTLINED if is_image else ft.Icons.VIDEOCAM_OUTLINED
        cut_label_str  = "Visual Style" if is_image else "How to Cut / Edit"
        cut_icon       = ft.Icons.PALETTE_OUTLINED if is_image else ft.Icons.CONTENT_CUT

        def _copy_image_prompt(e) -> None:
            prompt_text = (entry.get("image_prompt") or "").strip()
            if prompt_text:
                self.page.set_clipboard(prompt_text)
                self._snack("Image prompt copied to clipboard!")

        image_prompt_section: list[ft.Control] = []
        if is_image:
            image_prompt_section = [
                ft.Container(height=2),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=12, color=T.INFO),
                        ft.Text("IMAGE GENERATION PROMPT", size=9, weight=ft.FontWeight.W_700,
                                color=T.TEXT_MUTED, style=ft.TextStyle(letter_spacing=1.1)),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Copy",
                            icon=ft.Icons.COPY_OUTLINED,
                            on_click=_copy_image_prompt,
                            style=ft.ButtonStyle(
                                color=T.INFO,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                            ),
                        ),
                    ],
                    spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                entry["image_prompt_f"],
            ]

        card = ft.Container(
            content=ft.Column(
                controls=[
                    # Row 1: type badge + format chips + open + folder + delete
                    ft.Row(
                        controls=[
                            ft.Icon(type_icon, size=12, color=type_color),
                            type_badge,
                            *fmt_chips,
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.OPEN_IN_FULL,
                                icon_size=15, icon_color=T.ACCENT_LIGHT,
                                tooltip="Open detail",
                                on_click=_open_detail,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                    padding=4,
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.FOLDER_OPEN_OUTLINED, icon_size=15,
                                icon_color=T.TEXT_MUTED, tooltip="Open idea folder",
                                on_click=_open_folder,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                    padding=4,
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_size=15, icon_color=T.ERROR,
                                on_click=_remove, tooltip="Remove slot",
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": "#3a1010"},
                                    padding=4,
                                ),
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # Row 2: pub status + scheduled date + calendar pick button
                    ft.Row(
                        controls=[
                            *status_chips,
                            ft.Container(expand=True),
                            ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=11, color=T.TEXT_MUTED),
                            ft.Container(content=entry["sched_f"], width=120),
                            ft.IconButton(
                                icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                                icon_size=15, icon_color=T.TEXT_MUTED,
                                tooltip="Pick date",
                                on_click=_pick_date,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                    padding=4,
                                ),
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    T.divider(),
                    _form_label("Title", ft.Icons.TITLE),
                    entry["title_f"],
                    ft.Container(height=2),
                    _form_label("Hook", ft.Icons.LIGHTBULB_OUTLINE),
                    entry["concept_f"],
                    ft.Container(height=2),
                    _form_label(film_label_str, film_icon),
                    entry["film_f"],
                    ft.Container(height=2),
                    _form_label(cut_label_str, cut_icon),
                    entry["cut_f"],
                    *image_prompt_section,
                ],
                spacing=6,
            ),
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, T.BORDER if not is_image else "#1a2a3a"),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
        )
        entry["card"] = card
        return card

    def _add_slot(self) -> None:
        entry = self._entry_from_dict({"id": str(uuid4())})
        self._idea_entries.append(entry)
        self._ideas_col.controls.append(self._build_slot_card(entry))
        try:
            self._ideas_col.update()
        except Exception:
            pass
        self._maybe_refresh_calendar()
        self._persist_ideas()

    def _add_idea(self) -> None:
        self._add_slot()

    def _remove_idea(self, entry: dict) -> None:
        if entry in self._idea_entries:
            self._idea_entries.remove(entry)
            card = entry.get("card")
            if card and card in self._ideas_col.controls:
                self._ideas_col.controls.remove(card)
            try:
                self._ideas_col.update()
            except Exception:
                pass
            self._maybe_refresh_calendar()
            self._persist_ideas()

    # ── AI idea generation ──────────────────────────────────────────────────────

    def _stop_generation(self) -> None:
        if self._gen_stop_event:
            self._gen_stop_event.set()
        if self._gen_btn:
            self._gen_btn.disabled = False
        if self._gen_stop_btn:
            self._gen_stop_btn.visible = False
        if self._gen_status:
            self._gen_status.value   = "Generation stopped."
            self._gen_status.color   = T.TEXT_MUTED
            self._gen_status.visible = True
        try: self.page.update()
        except Exception: pass

    def _generate_ideas(self, e=None) -> None:
        provider_name = self._gen_selected_provider or "ollama"
        model_name    = self._gen_selected_model or ""

        # Guard: if ollama selected but not running
        if provider_name == "ollama" and (model_name == "__none__" or not is_ollama_running()):
            if self._gen_status:
                self._gen_status.value   = "Ollama not running — start it with: ollama serve"
                self._gen_status.color   = T.ERROR
                self._gen_status.visible = True
                try: self._gen_status.update()
                except Exception: pass
            return

        # Set up stop event
        self._gen_stop_event = threading.Event()

        if self._gen_btn:
            self._gen_btn.disabled = True
            try: self._gen_btn.update()
            except Exception: pass
        if self._gen_stop_btn:
            self._gen_stop_btn.visible = True
            try: self._gen_stop_btn.update()
            except Exception: pass
        if self._gen_status:
            _label   = f"[{provider_name}] {model_name}" if model_name else provider_name
            _n_total = self._gen_videos_per_day * self._gen_duration_days
            self._gen_status.value   = f"Generating {_n_total} ideas with {_label}…"
            self._gen_status.color   = T.TEXT_MUTED
            self._gen_status.visible = True
            try: self._gen_status.update()
            except Exception: pass

        def _run() -> None:
            # Capture our own stop event so the finally block can't interfere
            # with a new generation that starts after stop is clicked.
            my_stop_event = self._gen_stop_event
            try:
                if my_stop_event and my_stop_event.is_set():
                    return

                campaign     = self._selected
                product_name = (self._d_product_name_f.value or "").strip() if self._d_product_name_f else ""
                product_desc = (self._d_product_desc_f.value or "").strip() if self._d_product_desc_f else ""
                audience     = (self._d_audience_f.value     or "").strip() if self._d_audience_f     else ""
                cam_name     = campaign.name if campaign else ""
                strategy_lbl = _STRATEGY_LABELS.get(self._d_strategy or "", "")
                platforms_lbl = ", ".join(_PLATFORM_LABELS.get(p, p) for p in sorted(self._d_platforms))

                # === Gather brand & brief context from project ===
                project      = self.state.current_project
                brand_lines  : list[str] = []
                brief_lines  : list[str] = []
                product_lines: list[str] = []

                if project:
                    if project.name:
                        brand_lines.append(f"Brand: {project.name}")
                    if project.slogan:
                        brand_lines.append(f"Slogan: {project.slogan}")
                    if project.description:
                        brand_lines.append(f"Description: {project.description}")

                    try:
                        brief = json.loads(project.marketing_brief or "{}")
                    except Exception:
                        brief = {}

                    _brief_fields = [
                        ("target_audience", "Ideal Customer"),
                        ("pain_points",     "Pain Points"),
                        ("product_category","Product Category"),
                        ("key_benefits",    "Key Benefits"),
                        ("usp",             "Unique Selling Point"),
                        ("tone_of_voice",   "Tone of Voice"),
                        ("price_positioning","Price Positioning"),
                        ("social_proof",    "Social Proof"),
                        ("competitors",     "Competitors & Advantage"),
                        ("campaign_goal",   "Campaign Goal"),
                        ("geography",       "Target Geography"),
                        ("offer_hook",      "Offer / CTA"),
                    ]
                    for key, label in _brief_fields:
                        val = (brief.get(key) or "").strip()
                        if val:
                            brief_lines.append(f"{label}: {val}")

                    # Products linked to this campaign (from catalog)
                    if self._d_product_ids:
                        all_prods = product_repo.get_products(project.id)
                        for p in all_prods:
                            if p.id in self._d_product_ids:
                                line = f"• {p.name}"
                                if p.price:
                                    line += f" — {p.price}"
                                if p.description:
                                    line += f"\n  {p.description}"
                                product_lines.append(line)

                # Fallback to legacy campaign product fields
                if not product_lines and (product_name or product_desc):
                    line = f"• {product_name or '(unnamed)'}"
                    if product_desc:
                        line += f"\n  {product_desc}"
                    product_lines.append(line)

                brand_block    = "\n".join(brand_lines)    or "No brand profile filled yet."
                brief_block    = "\n".join(brief_lines)    or "No marketing brief filled yet."
                products_block = "\n".join(product_lines)  or "No products specified."

                # === Compute count ===
                n_ideas = self._gen_videos_per_day * self._gen_duration_days
                vpd     = max(self._gen_videos_per_day, 1)
                content_type = self._gen_content_type  # "mixed", "video", "image"

                existing_parts = []
                for i, ent in enumerate(self._idea_entries, 1):
                    t = ent.get("title", "").strip() or (ent["title_f"].value if "title_f" in ent else "").strip()
                    c = ent.get("concept", "").strip() or (ent["concept_f"].value if "concept_f" in ent else "").strip()
                    if t or c:
                        existing_parts.append(f"{i}. {t + ': ' if t else ''}{c}")
                existing_block = "\n".join(existing_parts) if existing_parts else "None yet."

                _common_header = f"""You are a social media content strategist. Every idea must be 100% specific to this exact brand and its real products — never generic.

=== BRAND ===
{brand_block}

=== MARKETING BRIEF ===
{brief_block}

=== PRODUCTS TO PROMOTE ===
{products_block}

=== CAMPAIGN ===
Campaign: {cam_name}
Strategy: {strategy_lbl or "Not specified"}
Platforms: {platforms_lbl or "Not specified"}
Target Audience: {audience or "See brief above"}
Schedule: {n_ideas} ideas over {self._gen_duration_days} days ({vpd}/day)

=== ALREADY SCHEDULED — do NOT repeat ===
{existing_block}"""

                if content_type == "video":
                    prompt = f"""{_common_header}

Generate EXACTLY {n_ideas} VIDEO ad ideas. Each must be deeply specific to the brand, products, tone, and audience above.

For each idea output EXACTLY:

TYPE: video
TITLE: [max 8 words — catchy, brand-specific]
CONCEPT: [hook, core message, why it resonates with this audience — 2-4 sentences]
HOW TO FILM: [camera, location, props, lighting, movement — 2-3 sentences]
HOW TO CUT: [editing style, pacing, music mood, captions, transitions — 2-3 sentences]
---

Output EXACTLY {n_ideas} ideas separated by ---. No other text."""

                elif content_type == "image":
                    prompt = f"""{_common_header}

Generate EXACTLY {n_ideas} IMAGE/SLIDESHOW ad ideas (static images or carousels). Each must be deeply specific to the brand, products, tone, and audience above. Include a detailed image generation prompt for each idea.

For each idea output EXACTLY:

TYPE: image
TITLE: [max 8 words — catchy, brand-specific]
CONCEPT: [hook, core message, why it resonates with this audience — 2-4 sentences]
SCENES: [describe each slide or scene in the slideshow — what images to show, composition, 2-3 sentences]
STYLE: [visual style, color palette, mood, text overlays, typography — 2-3 sentences]
IMAGE PROMPT: add reference image of the product and prompt: [detailed AI image generation prompt describing the scene, lighting, style, and product placement — 1-2 sentences]
---

Output EXACTLY {n_ideas} ideas separated by ---. No other text."""

                else:
                    n_video = n_ideas // 2
                    n_image = n_ideas - n_video
                    prompt = f"""{_common_header}

Generate EXACTLY {n_ideas} ad ideas: {n_video} video ideas and {n_image} image/slideshow ideas, alternating between them. Each must be deeply specific to the brand, products, tone, and audience above.

For VIDEO ideas output EXACTLY:

TYPE: video
TITLE: [max 8 words — catchy, brand-specific]
CONCEPT: [hook, core message, why it resonates with this audience — 2-4 sentences]
HOW TO FILM: [camera, location, props, lighting, movement — 2-3 sentences]
HOW TO CUT: [editing style, pacing, music mood, captions, transitions — 2-3 sentences]
---

For IMAGE/SLIDESHOW ideas output EXACTLY:

TYPE: image
TITLE: [max 8 words — catchy, brand-specific]
CONCEPT: [hook, core message, why it resonates with this audience — 2-4 sentences]
SCENES: [describe each slide or scene in the slideshow — what images to show, composition, 2-3 sentences]
STYLE: [visual style, color palette, mood, text overlays, typography — 2-3 sentences]
IMAGE PROMPT: add reference image of the product and prompt: [detailed AI image generation prompt — 1-2 sentences]
---

Output EXACTLY {n_ideas} ideas (alternating video/image) separated by ---. No other text."""

                # Resolve provider
                if provider_name == "ollama":
                    prov = OllamaProvider()
                else:
                    try:
                        prov = get_provider(provider_name)
                    except Exception as ex:
                        if self._gen_status:
                            self._gen_status.value = f"Provider error: {ex}"
                            self._gen_status.color = T.ERROR
                        return

                result = prov.generate(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name if model_name and model_name != "__none__" else None,
                    max_tokens=min(8000, max(1600, n_ideas * 320)),
                )

                if my_stop_event and my_stop_event.is_set():
                    return

                if result.error:
                    if self._gen_status:
                        self._gen_status.value = f"Error: {result.error[:100]}"
                        self._gen_status.color = T.ERROR
                else:
                    new_ideas = self._parse_generated_ideas(result.content)
                    for idea in new_ideas:
                        entry = self._entry_from_dict(idea)
                        self._idea_entries.append(entry)
                        self._ideas_col.controls.append(self._build_slot_card(entry))
                    n = len(new_ideas)
                    self._persist_ideas()
                    if self._gen_status:
                        self._gen_status.value = f"Added {n} idea{'s' if n != 1 else ''} ({vpd}/day · {self._gen_duration_days} days)."
                        self._gen_status.color = T.SUCCESS
                    self._maybe_refresh_calendar()
                    try: self.page.update()
                    except Exception: pass

            except Exception as ex:
                if self._gen_status:
                    self._gen_status.value = f"Error: {ex}"
                    self._gen_status.color = T.ERROR
            finally:
                # Only reset button state if stop wasn't already handled by _stop_generation().
                if not (my_stop_event and my_stop_event.is_set()):
                    if self._gen_btn:
                        self._gen_btn.disabled = False
                    if self._gen_stop_btn:
                        self._gen_stop_btn.visible = False
                    if self._gen_status:
                        self._gen_status.visible = True
                    try: self.page.update()
                    except Exception: pass

        threading.Thread(target=_run, daemon=True).start()

    def _parse_generated_ideas(self, text: str) -> list[dict]:
        ideas  = []
        # Split on any run of 3+ dashes that sits on its own line (or inline)
        blocks = [b.strip() for b in re.split(r'(?m)(?:^|\n)\s*-{3,}\s*(?:\n|$)', text) if b.strip()]
        # Fallback: if the model didn't use --- separators but packed all ideas
        # into one block, split on TITLE: lines instead.
        if len(blocks) == 1:
            sub: list[str] = []
            cur: list[str] = []
            for line in blocks[0].split("\n"):
                if line.strip().upper().startswith("TITLE:") and cur:
                    sub.append("\n".join(cur))
                    cur = [line]
                else:
                    cur.append(line)
            if cur:
                sub.append("\n".join(cur))
            if len(sub) > 1:
                blocks = [b.strip() for b in sub if b.strip()]
        for block in blocks:
            idea = {
                "id": str(uuid4()), "idea_type": "video",
                "title": "", "concept": "", "how_to_film": "", "how_to_cut": "",
                "image_prompt": "",
            }
            current_key:   str | None    = None
            current_lines: list[str]     = []

            for raw_line in (block + "\nENDMARKER:").split("\n"):
                ls    = raw_line.strip()
                upper = ls.upper()
                new_key = None
                rest    = ""
                if upper.startswith("TYPE:"):
                    val = ls[5:].strip().lower()
                    idea["idea_type"] = "image" if "image" in val else "video"
                    continue
                elif upper.startswith("TITLE:"):
                    new_key, rest = "title",        ls[6:].strip()
                elif upper.startswith("CONCEPT:"):
                    new_key, rest = "concept",      ls[8:].strip()
                elif upper.startswith("HOW TO FILM:"):
                    new_key, rest = "how_to_film",  ls[12:].strip()
                elif upper.startswith("HOW TO CUT:"):
                    new_key, rest = "how_to_cut",   ls[11:].strip()
                elif upper.startswith("SCENES:"):
                    new_key, rest = "how_to_film",  ls[7:].strip()
                elif upper.startswith("STYLE:"):
                    new_key, rest = "how_to_cut",   ls[6:].strip()
                elif upper.startswith("IMAGE PROMPT:"):
                    new_key, rest = "image_prompt", ls[13:].strip()
                elif upper.startswith("ENDMARKER:"):
                    new_key = "__end__"

                if new_key:
                    if current_key and current_key != "__end__":
                        idea[current_key] = " ".join(current_lines).strip()
                    current_key   = new_key
                    current_lines = [rest] if rest else []
                elif current_key and ls:
                    current_lines.append(ls)

            if idea["title"] or idea["concept"]:
                ideas.append(idea)
        return ideas

    def _persist_ideas(self) -> None:
        """Persist current idea entries to DB without touching other campaign fields."""
        c = self._selected
        if c is None:
            return
        video_ideas_data = [
            {
                "id":            ent["id"],
                "idea_type":     ent.get("idea_type", "video"),
                "title":         ent.get("title", "").strip(),
                "concept":       ent.get("concept", "").strip(),
                "how_to_film":   ent.get("how_to_film", "").strip(),
                "how_to_cut":    ent.get("how_to_cut", "").strip(),
                "image_prompt":  ent.get("image_prompt", "").strip(),
                "scheduled_date":ent.get("scheduled_date", "").strip(),
                "format":        ent.get("format",    "reel"),
                "pub_status":    ent.get("pub_status", "draft"),
            }
            for ent in self._idea_entries
        ]
        c.video_ideas = json.dumps(video_ideas_data)
        try:
            campaign_repo.update_campaign(c)
            self._ensure_idea_folders(c, video_ideas_data)
        except Exception:
            pass

    def _persist_product_ids(self) -> None:
        """Persist the current product-ID selection to DB."""
        c = self._selected
        if c is None:
            return
        c.product_ids = json.dumps(sorted(self._d_product_ids))
        try:
            campaign_repo.update_campaign(c)
        except Exception:
            pass

    # ── Selection ───────────────────────────────────────────────────────────────

    def _select_campaign(self, c: Campaign) -> None:
        self._auto_save_campaign(refresh_list=True)

        if self._selected and self._selected.id in self._campaign_cards:
            old = self._campaign_cards[self._selected.id]
            old.bgcolor = T.BG_CARD
            old.border  = ft.border.all(1, T.BORDER)
            try: old.update()
            except Exception: pass

        self._selected = c
        if c.id in self._campaign_cards:
            card = self._campaign_cards[c.id]
            card.bgcolor = T.ACCENT_DIM
            card.border  = ft.border.all(1, T.ACCENT_LIGHT)
            try: card.update()
            except Exception: pass

        self._load_detail(c)

    def _deselect(self) -> None:
        self._auto_save_campaign(refresh_list=True)
        if self._selected and self._selected.id in self._campaign_cards:
            old = self._campaign_cards[self._selected.id]
            old.bgcolor = T.BG_CARD
            old.border  = ft.border.all(1, T.BORDER)
            try: old.update()
            except Exception: pass
        self._selected = None
        self._idea_entries.clear()
        self._ideas_col.controls.clear()
        self._right.content = self._build_create_panel()
        try: self._right.update()
        except Exception: pass

    # ── Rename dialog ───────────────────────────────────────────────────────────

    def _rename_campaign_dialog(self, c: Campaign) -> None:
        name_f = _tf("Campaign Name", "", value=c.name)

        def _save(e):
            new_name = (name_f.value or "").strip()
            if not new_name:
                name_f.error_text = "Name is required"
                name_f.update()
                return
            c.name = new_name
            campaign_repo.update_campaign(c)
            dlg.open = False
            self.page.update()
            self._refresh()
            # update inline header field if this campaign is open
            if self._selected and self._selected.id == c.id and self._d_name_f:
                self._d_name_f.value = new_name
                try: self._d_name_f.update()
                except Exception: pass
            self._snack(f'Renamed to "{new_name}"')

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rename Campaign", color=T.TEXT_PRIMARY,
                          size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[name_f],
                spacing=10, tight=True, width=380,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Rename", on_click=_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ── Delete dialog ───────────────────────────────────────────────────────────

    def _confirm_delete(self, c: Campaign) -> None:
        def _do_delete(e):
            campaign_repo.delete_campaign(c.id)
            dlg.open = False
            self.page.update()
            self._deselect()
            self._refresh()

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Campaign?", color=T.ERROR, size=15, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Text(f'"{c.name}" and all its ad slots will be permanently deleted.',
                            color=T.TEXT_SECONDARY, size=13),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                ft.ElevatedButton("Delete", on_click=_do_delete, style=ft.ButtonStyle(
                    bgcolor={"": T.ERROR, "hovered": "#cc0000"}, color="#ffffff",
                    shape=ft.RoundedRectangleBorder(radius=8),
                )),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ── Folder management ───────────────────────────────────────────────────────

    def _workspace_root(self) -> Path:
        return Path(__file__).parent.parent / "workspace" / "campaigns"

    def _campaign_folder(self, campaign: Campaign) -> Path:
        proj = self.state.current_project
        proj_part = _safe_name(proj.name) if proj else "project"
        return self._workspace_root() / proj_part / _safe_name(campaign.name)

    def _idea_folder(self, campaign: Campaign, idea_title: str, idea_id: str) -> Path:
        folder_name = _safe_name(idea_title) if idea_title.strip() else f"idea_{idea_id[:8]}"
        return self._campaign_folder(campaign) / folder_name

    def _ensure_idea_folders(self, campaign: Campaign, ideas_data: list[dict]) -> None:
        self._campaign_folder(campaign).mkdir(parents=True, exist_ok=True)
        for idea in ideas_data:
            title   = idea.get("title", "")
            idea_id = idea.get("id", str(uuid4()))
            self._idea_folder(campaign, title, idea_id).mkdir(parents=True, exist_ok=True)

    def _open_idea_folder(self, entry: dict) -> None:
        campaign = self._selected
        if not campaign:
            self._snack("No campaign selected.", error=True)
            return
        title   = (entry["title_f"].value or "").strip()
        idea_id = entry["id"]
        path = self._idea_folder(campaign, title, idea_id)
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                is_wsl = (
                    Path("/proc/version").exists()
                    and "microsoft" in Path("/proc/version").read_text().lower()
                )
                if is_wsl:
                    subprocess.Popen(["explorer.exe", str(path)])
                else:
                    subprocess.Popen(["xdg-open", str(path)])
        except Exception as ex:
            self._snack(f"Folder created at: {path}\n(Auto-open failed: {ex})")

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _build_calendar_content(self) -> ft.Column:
        import calendar as _cal
        self._cal_header_text = ft.Text(
            f"{_cal.month_name[self._cal_month]} {self._cal_year}",
            size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY,
        )
        self._cal_grid_container = ft.Container()
        self._refresh_calendar_grid()

        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT, icon_size=20, icon_color=T.TEXT_MUTED,
                    on_click=lambda e: self._cal_prev_month(),
                    style=ft.ButtonStyle(
                        overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                    ),
                ),
                ft.Container(
                    content=self._cal_header_text, expand=True,
                    alignment=ft.alignment.center,
                ),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT, icon_size=20, icon_color=T.TEXT_MUTED,
                    on_click=lambda e: self._cal_next_month(),
                    style=ft.ButtonStyle(
                        overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                    ),
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        total = len(self._idea_entries)
        scheduled = sum(
            1 for e in self._idea_entries
            if (e.get("scheduled_date") or (e["sched_f"].value if "sched_f" in e else "")).strip()
        )
        subtitle = (
            ft.Text(
                f"{scheduled} of {total} slot{'s' if total != 1 else ''} scheduled",
                size=10, color=T.TEXT_MUTED,
            )
            if total else ft.Container()
        )

        return ft.Column(
            controls=[
                header,
                subtitle,
                ft.Container(height=4),
                self._cal_grid_container,
                ft.Container(height=40),
            ],
            spacing=6,
        )

    def _refresh_calendar_grid(self) -> None:
        import calendar as _cal
        if self._cal_grid_container is None:
            return

        date_map: dict[str, list[dict]] = {}
        for entry in self._idea_entries:
            d = (entry.get("scheduled_date") or (entry["sched_f"].value if "sched_f" in entry else "")).strip()
            if d:
                date_map.setdefault(d, []).append(entry)

        today_str = date.today().isoformat()
        cal_weeks = _cal.monthcalendar(self._cal_year, self._cal_month)

        dow_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(day, size=9, color=T.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600,
                                    text_align=ft.TextAlign.CENTER),
                    expand=True, alignment=ft.alignment.center,
                )
                for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            ],
            spacing=4,
        )

        week_rows = []
        for week in cal_weeks:
            cells = []
            for day in week:
                if day == 0:
                    cells.append(ft.Container(expand=True, height=68))
                    continue

                day_str = f"{self._cal_year}-{self._cal_month:02d}-{day:02d}"
                day_entries = date_map.get(day_str, [])
                is_today = (day_str == today_str)

                vid_chips = []
                for ent in day_entries[:3]:
                    title = (ent.get("title") or (ent["title_f"].value if "title_f" in ent else "")).strip() or "Untitled"
                    status = ent.get("pub_status", "in_progress")
                    chip_color = {
                        "posted":      T.SUCCESS,
                        "done":        T.INFO,
                        "in_progress": T.WARNING,
                    }.get(status, T.TEXT_MUTED)

                    def _open_ent(e, en=ent):
                        self._open_video_detail_dialog(en)

                    vid_chips.append(
                        ft.Container(
                            content=ft.Text(
                                title[:15] + ("…" if len(title) > 15 else ""),
                                size=8, color=chip_color,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            bgcolor=T.BG_SECONDARY,
                            border=ft.border.all(1, chip_color),
                            border_radius=4,
                            padding=ft.padding.symmetric(horizontal=4, vertical=2),
                            on_click=_open_ent,
                            ink=True,
                        )
                    )
                if len(day_entries) > 3:
                    vid_chips.append(
                        ft.Text(f"+{len(day_entries) - 3}", size=8, color=T.TEXT_MUTED)
                    )

                day_num = ft.Container(
                    content=ft.Text(
                        str(day), size=11,
                        color=T.ACCENT_LIGHT if is_today else (
                            T.TEXT_PRIMARY if day_entries else T.TEXT_MUTED
                        ),
                        weight=ft.FontWeight.BOLD if is_today else ft.FontWeight.NORMAL,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    bgcolor=T.ACCENT_DIM if is_today else ft.Colors.TRANSPARENT,
                    border_radius=11, width=22, height=22,
                    alignment=ft.alignment.center,
                )

                cell = ft.Container(
                    content=ft.Column(
                        controls=[day_num, *vid_chips],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    ),
                    expand=True,
                    bgcolor=T.BG_CARD if day_entries else ft.Colors.TRANSPARENT,
                    border=ft.border.all(1, T.BORDER if day_entries else ft.Colors.TRANSPARENT),
                    border_radius=6,
                    padding=ft.padding.all(4),
                    height=68,
                )
                cells.append(cell)

            week_rows.append(
                ft.Row(
                    controls=cells, spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )

        grid = ft.Column(controls=[dow_row, *week_rows], spacing=4)
        self._cal_grid_container.content = grid
        try:
            self._cal_grid_container.update()
        except Exception:
            pass

    def _cal_prev_month(self) -> None:
        if self._cal_month == 1:
            self._cal_month = 12
            self._cal_year -= 1
        else:
            self._cal_month -= 1
        self._update_cal_header()
        self._refresh_calendar_grid()

    def _cal_next_month(self) -> None:
        if self._cal_month == 12:
            self._cal_month = 1
            self._cal_year += 1
        else:
            self._cal_month += 1
        self._update_cal_header()
        self._refresh_calendar_grid()

    def _update_cal_header(self) -> None:
        import calendar as _cal
        if self._cal_header_text:
            self._cal_header_text.value = (
                f"{_cal.month_name[self._cal_month]} {self._cal_year}"
            )
            try:
                self._cal_header_text.update()
            except Exception:
                pass

    def _maybe_refresh_calendar(self) -> None:
        if self._d_tab == "calendar" and self._cal_grid_container is not None:
            self._refresh_calendar_grid()

    def _open_video_detail_dialog(self, entry: dict) -> None:
        title_val   = (entry["title_f"].value   or "").strip()
        concept_val = (entry["concept_f"].value or "").strip()
        film_val    = (entry["film_f"].value    or "").strip()
        cut_val     = (entry["cut_f"].value     or "").strip()
        sched_val   = (entry["sched_f"].value   or "").strip()

        t_f  = _tf("Title", "Short catchy title", value=title_val)
        c_f  = _tf("Concept / Hook", "Hook and message…",
                   value=concept_val, multiline=True, min_lines=3, max_lines=8)
        fm_f = _tf("How to Film", "Camera, location, props…",
                   value=film_val, multiline=True, min_lines=3, max_lines=6)
        cu_f = _tf("How to Cut / Edit", "Editing, pacing, music…",
                   value=cut_val, multiline=True, min_lines=3, max_lines=6)
        s_f  = _tf("Publish Date", "YYYY-MM-DD", value=sched_val)

        def _save(e):
            entry["title"]          = t_f.value  or ""
            entry["concept"]        = c_f.value  or ""
            entry["how_to_film"]    = fm_f.value or ""
            entry["how_to_cut"]     = cu_f.value or ""
            entry["scheduled_date"] = s_f.value  or ""
            entry["title_f"].value   = entry["title"]
            entry["concept_f"].value = entry["concept"]
            entry["film_f"].value    = entry["how_to_film"]
            entry["cut_f"].value     = entry["how_to_cut"]
            entry["sched_f"].value   = entry["scheduled_date"]
            for fld in (entry["title_f"], entry["concept_f"],
                        entry["film_f"], entry["cut_f"], entry["sched_f"]):
                try: fld.update()
                except Exception: pass
            dlg.open = False
            self.page.update()
            self._persist_ideas()
            self._maybe_refresh_calendar()

        def _close(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VIDEOCAM_OUTLINED, size=16, color=T.ACCENT_LIGHT),
                    ft.Text(
                        title_val or "Untitled Video",
                        size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY,
                        expand=True, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[
                    t_f,
                    ft.Container(height=2),
                    _form_label("Concept / Hook", ft.Icons.LIGHTBULB_OUTLINE),
                    c_f,
                    ft.Container(height=2),
                    _form_label("How to Film", ft.Icons.VIDEOCAM_OUTLINED),
                    fm_f,
                    ft.Container(height=2),
                    _form_label("How to Cut / Edit", ft.Icons.CONTENT_CUT),
                    cu_f,
                    ft.Container(height=2),
                    _form_label("Publish Date", ft.Icons.CALENDAR_TODAY_OUTLINED),
                    s_f,
                ],
                spacing=6, tight=True, width=520,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Close", on_click=_close,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Save Changes", on_click=_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _open_date_picker_dialog(self, entry: dict) -> None:
        try:
            initial = date.fromisoformat((entry["sched_f"].value or "").strip())
        except Exception:
            initial = date.today()

        sel_date   = [initial]
        disp_year  = [initial.year]
        disp_month = [initial.month]

        grid_box = ft.Container(width=308)
        hdr_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY)
        sel_text = ft.Text("", size=11, color=T.ACCENT_LIGHT)

        def _render():
            import calendar as _cal
            hdr_text.value = f"{_cal.month_name[disp_month[0]]} {disp_year[0]}"
            weeks = _cal.monthcalendar(disp_year[0], disp_month[0])

            dow_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(d, size=9, color=T.TEXT_MUTED,
                                        text_align=ft.TextAlign.CENTER),
                        width=40, alignment=ft.alignment.center,
                    )
                    for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
                ],
                spacing=2,
            )
            rows = [dow_row]
            for week in weeks:
                btns = []
                for day in week:
                    if day == 0:
                        btns.append(ft.Container(width=40, height=36))
                        continue
                    is_sel = (
                        day == sel_date[0].day and
                        disp_month[0] == sel_date[0].month and
                        disp_year[0] == sel_date[0].year
                    )

                    def _pick(e, d=day):
                        try:
                            sel_date[0] = date(disp_year[0], disp_month[0], d)
                        except Exception:
                            return
                        sel_text.value = f"Selected: {sel_date[0].isoformat()}"
                        try: sel_text.update()
                        except Exception: pass
                        _render()
                        try: grid_box.update()
                        except Exception: pass
                        try: hdr_text.update()
                        except Exception: pass

                    btns.append(
                        ft.Container(
                            content=ft.Text(
                                str(day), size=11, text_align=ft.TextAlign.CENTER,
                                color=T.ACCENT_LIGHT if is_sel else T.TEXT_PRIMARY,
                            ),
                            width=40, height=36,
                            bgcolor=T.ACCENT_DIM if is_sel else ft.Colors.TRANSPARENT,
                            border=ft.border.all(1, T.ACCENT_LIGHT if is_sel else ft.Colors.TRANSPARENT),
                            border_radius=6,
                            alignment=ft.alignment.center,
                            on_click=_pick,
                            ink=True,
                        )
                    )
                rows.append(ft.Row(controls=btns, spacing=2))
            grid_box.content = ft.Column(controls=rows, spacing=3)

        def _prev(e):
            if disp_month[0] == 1:
                disp_month[0] = 12; disp_year[0] -= 1
            else:
                disp_month[0] -= 1
            _render()
            try: grid_box.update()
            except Exception: pass
            try: hdr_text.update()
            except Exception: pass

        def _next(e):
            if disp_month[0] == 12:
                disp_month[0] = 1; disp_year[0] += 1
            else:
                disp_month[0] += 1
            _render()
            try: grid_box.update()
            except Exception: pass
            try: hdr_text.update()
            except Exception: pass

        _render()
        sel_text.value = f"Selected: {sel_date[0].isoformat()}"

        def _confirm(e):
            iso = sel_date[0].isoformat()
            entry["scheduled_date"] = iso
            entry["sched_f"].value  = iso
            try: entry["sched_f"].update()
            except Exception: pass
            dlg.open = False
            self.page.update()
            self._persist_ideas()
            self._maybe_refresh_calendar()

        def _cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Pick a Date", color=T.TEXT_PRIMARY,
                          size=14, weight=ft.FontWeight.BOLD),
            bgcolor=T.BG_CARD,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT, icon_size=18, icon_color=T.TEXT_MUTED,
                                on_click=_prev,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                ),
                            ),
                            ft.Container(content=hdr_text, expand=True,
                                         alignment=ft.alignment.center),
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_RIGHT, icon_size=18, icon_color=T.TEXT_MUTED,
                                on_click=_next,
                                style=ft.ButtonStyle(
                                    overlay_color={"": ft.Colors.TRANSPARENT, "hovered": T.ACCENT_DIM},
                                ),
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    grid_box,
                    ft.Container(
                        content=sel_text,
                        padding=ft.padding.only(left=4, top=2),
                    ),
                ],
                spacing=6, tight=True, width=320,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT_MUTED)),
                T.accent_button("Set Date", on_click=_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.overlay.clear()
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _get_campaigns(self) -> list[Campaign]:
        if not self.state.current_project:
            return []
        return campaign_repo.get_campaigns(self.state.current_project.id)

    def _refresh(self) -> None:
        campaigns = self._get_campaigns()
        total  = len(campaigns)
        active = sum(1 for c in campaigns if c.status == "active")
        paused = sum(1 for c in campaigns if c.status == "paused")
        if self._stat_total:
            self._stat_total.value  = str(total)
            self._stat_active.value = str(active)
            self._stat_paused.value = str(paused)
            try:
                self._stat_total.update()
                self._stat_active.update()
                self._stat_paused.update()
            except Exception:
                pass
        self._reload_list()

    def _snack(self, msg: str, error: bool = False) -> None:
        sb = ft.SnackBar(
            content=ft.Text(msg, color=T.TEXT_PRIMARY),
            bgcolor=T.ERROR if error else T.BG_CARD,
        )
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()


# ── Module helpers ─────────────────────────────────────────────────────────────

def _tf(
    label: str,
    hint: str = "",
    value: str = "",
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: int = 1,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines if multiline else 1,
        bgcolor=T.BG_INPUT,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        color=T.TEXT_PRIMARY,
        label_style=ft.TextStyle(color=T.TEXT_MUTED),
        hint_style=ft.TextStyle(color=T.TEXT_MUTED),
        cursor_color=T.ACCENT_LIGHT,
        border_radius=8,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=9),
        expand=True,
    )


def _inline_tf(value: str = "") -> ft.TextField:
    return ft.TextField(
        value=value,
        hint_text="Campaign name",
        bgcolor=ft.Colors.TRANSPARENT,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=T.ACCENT,
        color=T.TEXT_PRIMARY,
        cursor_color=T.ACCENT_LIGHT,
        border_radius=6,
        text_size=14,
        text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
        content_padding=ft.padding.symmetric(horizontal=6, vertical=4),
        expand=True,
    )


def _form_label(text: str, icon) -> ft.Row:
    return ft.Row(
        controls=[
            ft.Icon(icon, size=12, color=T.ACCENT_LIGHT),
            ft.Text(text.upper(), size=9, weight=ft.FontWeight.W_700,
                    color=T.TEXT_MUTED, style=ft.TextStyle(letter_spacing=1.1)),
        ],
        spacing=5,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _mini_stat(value: str, label: str, border_color: str) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(value, size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ft.Text(label, size=9, color=T.TEXT_MUTED),
            ],
            spacing=0, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=T.BG_CARD,
        border=ft.border.all(1, border_color),
        border_radius=8,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
    )


def _migrate_pub_status(status: str) -> str:
    """Map old status values to the current three-state scheme."""
    return {"draft": "in_progress", "ready": "done", "published": "posted"}.get(status, status)


def _parse_float(val: str | None) -> float:
    try:
        return float((val or "").replace(",", "").strip())
    except ValueError:
        return 0.0


def _safe_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:60] or "untitled"
