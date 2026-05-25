"""Brand identity editor — full main-area view."""
import re
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.project_repo import update_project

if TYPE_CHECKING:
    from ui.layout import AppLayout


def _parse_hex_colors(raw: str) -> list[str]:
    return re.findall(r"#[0-9a-fA-F]{3,8}", raw or "")


class BrandView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state = app.state
        self._swatch_row: ft.Row | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    def build(self) -> ft.Container:
        project = self.state.current_project
        if not project:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=T.TEXT_MUTED, size=44),
                        ft.Text("No project selected", color=T.TEXT_MUTED, size=14,
                                text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_500),
                        ft.Text(
                            "Create or select a project from the sidebar first.",
                            color=T.TEXT_MUTED, size=12, text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                expand=True,
                alignment=ft.alignment.center,
                bgcolor=T.BG_PRIMARY,
            )

        # ── Fields ────────────────────────────────────────────────────────────

        slogan_f = self._textfield(
            value=project.slogan,
            hint="Your brand's core promise in one line…",
            size=15,
        )

        desc_f = self._textfield(
            value=project.description,
            hint="What does your brand stand for? Who is it for? What makes it different?",
            multiline=True,
            min_lines=3,
            max_lines=6,
        )

        tone_f = self._textfield(
            value=project.tone_of_voice,
            hint="Conversational, witty, never corporate — always empowering and direct",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        values_f = self._textfield(
            value=project.brand_values,
            hint="Sustainability, Innovation, Transparency, Community",
        )

        self._swatch_row = self._build_swatch_row(project.brand_colors)

        def _on_colors_change(e):
            self._swatch_row.controls = self._build_swatch_row(colors_f.value).controls
            self._swatch_row.update()

        colors_f = self._textfield(
            value=project.brand_colors,
            hint="#7c3aed, #a78bfa, #0d0d1a — separate hex codes with commas",
            on_change=_on_colors_change,
        )

        fonts_f = self._textfield(
            value=project.fonts,
            hint="Inter, Playfair Display, Roboto Mono",
        )

        img_style_f = self._textfield(
            value=project.image_style,
            hint="Dark moody studio, bright lifestyle, flat lay product, cinematic close-ups…",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        # Audio & video fields
        voice_f = self._textfield(
            value=project.voiceover_voice,
            hint="ElevenLabs – Bella (warm, female, Gen-Z) · OpenAI – Nova · deep authoritative male",
        )

        music_f = self._textfield(
            value=project.music_mood,
            hint="Upbeat lo-fi for reels, cinematic orchestral for brand films, high-energy EDM for ads",
            multiline=True,
            min_lines=2,
            max_lines=3,
        )

        video_style_f = self._textfield(
            value=project.video_style,
            hint="Fast cuts with text overlays, UGC talking-head, cinematic B-roll, meme-format, ASMR…",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        # Audience & content fields
        audience_f = self._textfield(
            value=project.target_audience,
            hint="Women 22–35, interested in fitness & wellness, tier-1 cities, mid-high income",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        pillars_f = self._textfield(
            value=project.content_pillars,
            hint="Education, Behind the Scenes, Product Demos, Testimonials, Trending formats",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        hashtags_f = self._textfield(
            value=project.hashtags,
            hint="#yourbrand #niche #campaign — separate with spaces or commas",
            multiline=True,
            min_lines=2,
            max_lines=3,
        )

        # ── Save ──────────────────────────────────────────────────────────────

        def save_brand(e):
            project.slogan = slogan_f.value or ""
            project.description = desc_f.value or ""
            project.tone_of_voice = tone_f.value or ""
            project.brand_values = values_f.value or ""
            project.brand_colors = colors_f.value or ""
            project.fonts = fonts_f.value or ""
            project.image_style = img_style_f.value or ""
            project.voiceover_voice = voice_f.value or ""
            project.music_mood = music_f.value or ""
            project.video_style = video_style_f.value or ""
            project.target_audience = audience_f.value or ""
            project.content_pillars = pillars_f.value or ""
            project.hashtags = hashtags_f.value or ""
            update_project(project)
            self.state.refresh_projects()
            snack = ft.SnackBar(
                content=ft.Text("Brand identity saved", color=T.TEXT_PRIMARY),
                bgcolor=T.BG_CARD,
            )
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()

        # ── Layout ────────────────────────────────────────────────────────────

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_header(project),

                                self._section_card(
                                    icon=ft.Icons.RECORD_VOICE_OVER_OUTLINED,
                                    title="Brand Voice",
                                    subtitle="Slogan, positioning & tone",
                                    content=ft.Column(controls=[
                                        self._field_block("Slogan", slogan_f),
                                        self._field_block("Description", desc_f),
                                        self._field_block("Tone of Voice", tone_f),
                                        self._field_block("Brand Values", values_f),
                                    ], spacing=16),
                                ),

                                self._section_card(
                                    icon=ft.Icons.PALETTE_OUTLINED,
                                    title="Visual Identity",
                                    subtitle="Colors & typography",
                                    content=ft.Column(controls=[
                                        self._field_block(
                                            "Brand Colors",
                                            ft.Column(controls=[
                                                colors_f,
                                                self._swatch_row,
                                            ], spacing=8),
                                        ),
                                        self._field_block("Fonts", fonts_f),
                                    ], spacing=16),
                                ),

                                self._section_card(
                                    icon=ft.Icons.CAMERA_ALT_OUTLINED,
                                    title="Image Style",
                                    subtitle="Visual direction for photos & AI-generated media",
                                    content=self._field_block("Photo / Creative Direction", img_style_f),
                                ),

                                self._section_card(
                                    icon=ft.Icons.HEADPHONES_OUTLINED,
                                    title="Audio & Video",
                                    subtitle="Voice, music & motion direction for video content",
                                    content=ft.Column(controls=[
                                        self._field_block("Voiceover Voice", voice_f),
                                        self._field_block("Music Mood", music_f),
                                        self._field_block("Video Style", video_style_f),
                                    ], spacing=16),
                                ),

                                self._section_card(
                                    icon=ft.Icons.GROUP_OUTLINED,
                                    title="Audience & Content",
                                    subtitle="Who you speak to and what you consistently talk about",
                                    content=ft.Column(controls=[
                                        self._field_block("Target Audience", audience_f),
                                        self._field_block("Content Pillars", pillars_f),
                                        self._field_block("Default Hashtags", hashtags_f),
                                    ], spacing=16),
                                ),

                                ft.Container(
                                    content=T.accent_button(
                                        "Save Brand Identity",
                                        on_click=save_brand,
                                        icon=ft.Icons.SAVE_OUTLINED,
                                    ),
                                    padding=ft.padding.only(top=4, bottom=24),
                                ),
                            ],
                            spacing=16,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        padding=ft.padding.symmetric(horizontal=40, vertical=28),
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
            bgcolor=T.BG_PRIMARY,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_header(self, project) -> ft.Container:
        initials = "".join(w[0].upper() for w in project.name.split()[:2])
        return ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(
                        height=100,
                        border_radius=ft.border_radius.only(top_left=14, top_right=14),
                        gradient=ft.LinearGradient(
                            begin=ft.alignment.center_left,
                            end=ft.alignment.center_right,
                            colors=[T.ACCENT_DIM, "#1e1040", T.BG_PRIMARY],
                        ),
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(initials, size=24, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                    width=64,
                                    height=64,
                                    bgcolor=T.ACCENT,
                                    border_radius=16,
                                    alignment=ft.alignment.center,
                                    shadow=ft.BoxShadow(
                                        blur_radius=20,
                                        color="#5b21b660",
                                        offset=ft.Offset(0, 6),
                                    ),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(project.name, size=22, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.VERIFIED_OUTLINED, size=13, color=T.ACCENT_LIGHT),
                                                ft.Text("Brand Identity", size=12, color=T.ACCENT_LIGHT,
                                                        weight=ft.FontWeight.W_500),
                                            ],
                                            spacing=4,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=3,
                                    tight=True,
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(left=24, top=58),
                    ),
                ],
            ),
            border_radius=14,
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, T.BORDER),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            margin=ft.margin.only(bottom=4),
        )

    def _build_swatch_row(self, raw: str) -> ft.Row:
        colors = _parse_hex_colors(raw)
        if not colors:
            return ft.Row(
                controls=[
                    ft.Text("Enter hex codes above to preview swatches", size=11, color=T.TEXT_MUTED),
                ],
                spacing=0,
            )
        swatches = []
        for c in colors[:10]:
            swatches.append(
                ft.Tooltip(
                    message=c,
                    content=ft.Container(
                        width=32,
                        height=32,
                        bgcolor=c,
                        border_radius=8,
                        border=ft.border.all(1, T.BORDER),
                        shadow=ft.BoxShadow(blur_radius=8, color="#00000040", offset=ft.Offset(0, 2)),
                    ),
                )
            )
        return ft.Row(controls=swatches, spacing=8, wrap=True)

    def _section_card(self, icon: str, title: str, subtitle: str, content: ft.Control) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon, size=17, color=T.ACCENT_LIGHT),
                                width=38,
                                height=38,
                                bgcolor=T.ACCENT_DIM,
                                border_radius=10,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                                    ft.Text(subtitle, size=11, color=T.TEXT_MUTED),
                                ],
                                spacing=1,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=T.BORDER),
                    content,
                ],
                spacing=14,
            ),
            bgcolor=T.BG_CARD,
            border_radius=12,
            border=ft.border.all(1, T.BORDER),
            padding=ft.padding.all(20),
        )

    def _field_block(self, label: str, field: ft.Control) -> ft.Column:
        return ft.Column(
            controls=[
                ft.Text(
                    label.upper(),
                    size=10,
                    color=T.TEXT_MUTED,
                    weight=ft.FontWeight.W_700,
                    style=ft.TextStyle(letter_spacing=1.0),
                ),
                field,
            ],
            spacing=7,
            tight=True,
        )

    def _textfield(
        self,
        value: str = "",
        hint: str = "",
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
        size: int = 13,
        on_change=None,
    ) -> ft.TextField:
        return ft.TextField(
            value=value,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines if multiline else 1,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            cursor_color=T.ACCENT_LIGHT,
            border_radius=8,
            text_size=size,
            hint_text=hint,
            hint_style=ft.TextStyle(color=T.TEXT_MUTED),
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            on_change=on_change,
        )
