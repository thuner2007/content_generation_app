"""Marketing Brief — full main-area page with section cards."""
import json as _json
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.project_repo import update_project

if TYPE_CHECKING:
    from ui.layout import AppLayout


# (section_title, section_icon, [(key, label, icon, hint, multiline), ...])
_SECTIONS = [
    ("Customer Profile", ft.Icons.PEOPLE_OUTLINE, [
        ("target_audience", "Ideal Customer", ft.Icons.PERSON_OUTLINE,
         "Who buys this? Age, interests, job, lifestyle, behaviors…", True),
        ("pain_points", "Pain Points", ft.Icons.LIGHTBULB_OUTLINE,
         "What frustrations or problems does this solve for them?", True),
    ]),
    ("Product & Value", ft.Icons.INVENTORY_2, [
        ("product_category", "Product / Service Type", ft.Icons.CATEGORY,
         "e.g. SaaS, physical product, coaching, app, e-commerce…", False),
        ("key_benefits", "Key Benefits", ft.Icons.STAR_BORDER,
         "Top 3–5 benefits the customer actually gets (not just features)", True),
        ("usp", "Unique Selling Prop. (USP)", ft.Icons.BOLT_OUTLINED,
         "What makes this stand out from every competitor?", False),
    ]),
    ("Brand Voice", ft.Icons.PALETTE_OUTLINED, [
        ("tone_of_voice", "Tone of Voice", ft.Icons.RECORD_VOICE_OVER,
         "Professional / Casual / Exciting / Empathetic / Bold…", False),
        ("price_positioning", "Price Positioning", ft.Icons.ATTACH_MONEY,
         "Budget / Mid-range / Premium / Luxury", False),
        ("social_proof", "Social Proof", ft.Icons.VERIFIED,
         "Reviews, star ratings, certifications, press mentions", False),
    ]),
    ("Competition", ft.Icons.TRENDING_UP, [
        ("competitors", "Competitors & Advantage", ft.Icons.COMPARE_ARROWS,
         "Main rivals and exactly why you beat them", True),
    ]),
    ("Campaign", ft.Icons.CAMPAIGN_OUTLINED, [
        ("campaign_goal", "Campaign Goal", ft.Icons.FLAG,
         "Awareness / Lead gen / Direct sales / App installs / Engagement", False),
        ("geography", "Geography / Market", ft.Icons.LANGUAGE,
         "Country, city, or region you're selling in", False),
        ("offer_hook", "Offer / Hook / CTA", ft.Icons.LOCAL_OFFER,
         "Discount, free trial, guarantee, urgency element", False),
    ]),
]

_TOTAL_FIELDS = sum(len(fields) for _, _, fields in _SECTIONS) + 1  # +1 for description


class BriefView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state = app.state
        self._field_refs: dict[str, ft.TextField] = {}
        self._desc_field: ft.TextField | None = None

    def build(self) -> ft.Column:
        project = self.state.current_project

        if not project:
            return ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.CAMPAIGN_OUTLINED, size=44, color=T.TEXT_MUTED),
                                ft.Text(
                                    "No project selected",
                                    size=16, color=T.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(
                                    "Select or create a project from the sidebar to edit its marketing brief.",
                                    size=12, color=T.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        expand=True,
                        alignment=ft.alignment.center,
                        padding=40,
                    )
                ],
                expand=True,
            )

        try:
            brief = _json.loads(project.marketing_brief or "{}")
        except Exception:
            brief = {}

        desc_filled = 1 if project.description and project.description.strip() else 0
        brief_filled = sum(1 for v in brief.values() if v and str(v).strip())
        filled = desc_filled + brief_filled
        pct = int(filled / _TOTAL_FIELDS * 100)
        pct_color = _pct_color(pct)

        # ── Description field (full width, top of page) ───────────────────────
        self._desc_field = ft.TextField(
            value=project.description or "",
            multiline=True,
            min_lines=3,
            max_lines=6,
            bgcolor=T.BG_PRIMARY,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            hint_text="Describe your product or business in a few sentences. What do you sell, who is it for, and what is the goal of this project?",
            hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
            cursor_color=T.ACCENT_LIGHT,
            border_radius=8,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
        )

        self._field_refs = {}
        section_controls: list[ft.Control] = [
            self._section_header("Project Overview", ft.Icons.DESCRIPTION_OUTLINED),
            self._field_card("Project Description", ft.Icons.NOTES, self._desc_field),
        ]

        for section_title, section_icon, fields in _SECTIONS:
            section_controls.append(self._section_header(section_title, section_icon))

            for i in range(0, len(fields), 2):
                pair = fields[i : i + 2]
                cards = []
                for key, label, icon, hint, multiline in pair:
                    tf = ft.TextField(
                        value=brief.get(key, ""),
                        multiline=multiline,
                        min_lines=2 if multiline else 1,
                        max_lines=5 if multiline else 2,
                        bgcolor=T.BG_PRIMARY,
                        border_color=T.BORDER,
                        focused_border_color=T.ACCENT,
                        color=T.TEXT_PRIMARY,
                        hint_text=hint,
                        hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
                        cursor_color=T.ACCENT_LIGHT,
                        border_radius=8,
                        text_size=13,
                        content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    )
                    self._field_refs[key] = tf
                    cards.append(self._field_card(label, icon, tf))

                section_controls.append(ft.Row(controls=cards, spacing=12))

            section_controls.append(ft.Container(height=4))

        def save_brief(e):
            if self._desc_field:
                project.description = self._desc_field.value.strip()
            brief_data = {k: (tf.value or "").strip() for k, tf in self._field_refs.items()}
            project.marketing_brief = _json.dumps(brief_data)
            update_project(project)
            self.state.refresh_projects()
            self._snack("Marketing brief saved ✓")

        def start_interview(e):
            if not self.state.current_project:
                return
            self.state.current_view = "chat"
            self.app.show_chat_view()
            self.app.sidebar.refresh()
            self.app.chat_view.trigger_brief_interview()

        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.CAMPAIGN_OUTLINED, size=20, color=T.ACCENT_LIGHT),
                                width=40, height=40,
                                bgcolor=T.ACCENT_DIM,
                                border_radius=10,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Marketing Brief",
                                        size=17, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        f"{project.name}  ·  {filled} / {_TOTAL_FIELDS} fields filled",
                                        size=12, color=T.TEXT_MUTED,
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"{pct}%",
                                    size=12,
                                    color=pct_color,
                                    weight=ft.FontWeight.W_600,
                                ),
                                bgcolor=T.BG_CARD,
                                border=ft.border.all(1, pct_color),
                                border_radius=6,
                                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            ),
                            ft.OutlinedButton(
                                "AI Interview",
                                icon=ft.Icons.SMART_TOY_OUTLINED,
                                on_click=start_interview,
                                style=ft.ButtonStyle(
                                    color=T.ACCENT_LIGHT,
                                    side=ft.BorderSide(1, T.BORDER_ACCENT),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    bgcolor={"": T.ACCENT_DIM, "hovered": T.ACCENT},
                                    overlay_color=ft.Colors.TRANSPARENT,
                                ),
                            ),
                            T.accent_button("Save Brief", on_click=save_brief),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.ProgressBar(
                        value=filled / _TOTAL_FIELDS,
                        bgcolor=T.BG_CARD,
                        color=pct_color,
                        border_radius=4,
                        height=5,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            bgcolor=T.BG_SECONDARY,
        )

        return ft.Column(
            controls=[
                header,
                T.divider(),
                ft.Container(
                    content=ft.Column(
                        controls=section_controls,
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=24, vertical=14),
                ),
            ],
            spacing=0,
            expand=True,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_header(self, title: str, icon) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=14, color=T.ACCENT_LIGHT),
                    ft.Text(
                        title.upper(),
                        size=10,
                        weight=ft.FontWeight.W_700,
                        color=T.TEXT_MUTED,
                        style=ft.TextStyle(letter_spacing=1.2),
                    ),
                    ft.Container(
                        expand=True,
                        content=ft.Divider(height=1, color=T.BORDER),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(top=10, bottom=2),
        )

    def _field_card(self, label: str, icon, tf: ft.TextField) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(icon, size=13, color=T.ACCENT_LIGHT),
                            ft.Text(
                                label,
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=T.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    tf,
                ],
                spacing=6,
                tight=True,
            ),
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, T.BORDER),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            expand=True,
        )

    def _snack(self, msg: str) -> None:
        sb = ft.SnackBar(content=ft.Text(msg, color=T.TEXT_PRIMARY), bgcolor=T.BG_CARD)
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()


def _pct_color(pct: int) -> str:
    if pct >= 70:
        return T.SUCCESS
    if pct >= 30:
        return T.WARNING
    return T.ERROR
