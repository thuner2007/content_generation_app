"""Main chat workspace view."""
import json as _json
import threading
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.models import Message, Chat
from storage import chat_repo, asset_repo
from storage.project_repo import update_project as _update_project, get_project as _get_project
from core import dispatcher
from core.app_state import AppState
from ai_providers.router import list_providers, get_models_for_provider

if TYPE_CHECKING:
    from ui.layout import AppLayout

def _save_default(provider: str, model: str) -> None:
    from storage.settings_repo import set_setting
    try:
        set_setting("default_provider", provider)
        set_setting("default_model", model)
    except Exception:
        pass


_PROMO_KEYWORDS = (
    "promot", "advertis", "market my", "sell my", "sell this", "campaign for",
    "ad copy for", "ads for", "launch my", "boost sales", "drive traffic",
    "run ads", "facebook ad", "google ad", "instagram ad", "tiktok ad",
    "paid ad", "product launch", "create ad", "write ad", "make ad",
    "announce my", "spread the word",
)

# (key, label, hint, multiline)
_BRIEF_FIELDS = [
    ("target_audience",   "Target Audience",         "Who exactly are you targeting? Age, interests, profession, behavior…", True),
    ("usp",               "Unique Selling Prop.",     "What makes this different or better than every competitor?",           False),
    ("key_benefits",      "Key Benefits",             "Top 3–5 benefits the customer gets (not just features)",              True),
    ("pain_points",       "Pain Points",              "What frustrations, problems, or desires does this solve?",            True),
    ("tone_of_voice",     "Tone of Voice",            "Professional / Casual / Exciting / Empathetic / Bold…",              False),
    ("price_positioning", "Price Positioning",        "Budget / Mid-range / Premium / Luxury",                              False),
    ("competitors",       "Competitors & Advantage",  "Main competitors and why you win against them",                      False),
    ("social_proof",      "Social Proof",             "Reviews, ratings, certifications, press mentions, case studies",     False),
    ("campaign_goal",     "Campaign Goal",            "Awareness / Lead gen / Direct sales / App installs / Engagement",   False),
    ("geography",         "Geography / Market",       "Country, city, or region you're targeting",                         False),
    ("offer_hook",        "Offer / Hook / CTA",       "Special deal, free trial, guarantee, urgency element",              False),
    ("product_category",  "Product / Service Type",  "e.g. SaaS, e-commerce, coaching, app, physical product…",           False),
]


_BRIEF_FILL_KEYWORDS = (
    "fill out", "fill in", "fill the brief", "fill my brief", "complete the brief",
    "help me fill", "help fill", "fill for me", "help me with my target",
    "help me define", "help me with the usp", "help me with my usp",
    "help me with my audience", "what should my target", "who is my target",
    "help with target audience", "help with usp", "help with benefits",
    "help with pain points", "help me describe my", "define my target",
    "define my audience", "help me figure out",
)

_BRIEF_FILL_API_TEXT = (
    "I need help building my marketing brief. "
    "Please interview me like an experienced marketing coach — one short question at a time. "
    "After each answer I give: first give me 1-2 short, honest suggestions to make it stronger "
    "(I am not a sales expert, so be direct and helpful), then ask your next question. "
    "Wait for my answer before moving on. "
    "Cover: what my product or service is, who my ideal customer is, the main benefits, "
    "the problems it solves, what makes it stand out, the price range, the tone I want, "
    "my main competitors, my campaign goal, and any special offer or hook. "
    "Keep every question under 15 words. Keep feedback to 2-3 sentences max. "
    "Once all topics are covered, output a section titled '## Your Marketing Brief' "
    "with every field clearly labeled and filled in. Start with your first question now."
)

_FORMAT_BRIEF_API_TEXT = (
    "Based on everything we've discussed so far, please output a structured marketing brief. "
    "Use this exact format — one field per line, label followed by a colon:\n\n"
    "## Your Marketing Brief\n"
    "Target Audience: ...\n"
    "Pain Points: ...\n"
    "Product / Service Type: ...\n"
    "Key Benefits: ...\n"
    "USP: ...\n"
    "Tone of Voice: ...\n"
    "Price Positioning: ...\n"
    "Social Proof: ...\n"
    "Competitors & Advantage: ...\n"
    "Campaign Goal: ...\n"
    "Geography / Market: ...\n"
    "Offer / Hook / CTA: ...\n\n"
    "Fill in only the fields that came up in our conversation. Leave the rest blank."
)

_BRIEF_HEADINGS = (
    "## your marketing brief",
    "## marketing brief",
    "**your marketing brief**",
    "**marketing brief**",
    "# marketing brief",
    "your marketing brief:",
    "here is your marketing brief",
    "here's your marketing brief",
    "marketing brief summary",
)

# Label variants the AI might use → JSON key
_BRIEF_LABEL_MAP = {
    "ideal customer":          "target_audience",
    "target audience":         "target_audience",
    "customer profile":        "target_audience",
    "who buys":                "target_audience",
    "usp":                     "usp",
    "unique selling":          "usp",
    "stands out":              "usp",
    "differentiator":          "usp",
    "key benefits":            "key_benefits",
    "main benefits":           "key_benefits",
    "top benefits":            "key_benefits",
    "benefits":                "key_benefits",
    "pain points":             "pain_points",
    "problems solved":         "pain_points",
    "problems it solves":      "pain_points",
    "frustrations":            "pain_points",
    "tone of voice":           "tone_of_voice",
    "tone":                    "tone_of_voice",
    "communication style":     "tone_of_voice",
    "price positioning":       "price_positioning",
    "price range":             "price_positioning",
    "pricing":                 "price_positioning",
    "price":                   "price_positioning",
    "social proof":            "social_proof",
    "reviews":                 "social_proof",
    "testimonials":            "social_proof",
    "competitors & advantage": "competitors",
    "competitors":             "competitors",
    "competition":             "competitors",
    "main rivals":             "competitors",
    "campaign goal":           "campaign_goal",
    "goal":                    "campaign_goal",
    "objective":               "campaign_goal",
    "geography":               "geography",
    "geography / market":      "geography",
    "market":                  "geography",
    "location":                "geography",
    "offer / hook / cta":      "offer_hook",
    "offer":                   "offer_hook",
    "hook":                    "offer_hook",
    "cta":                     "offer_hook",
    "special offer":           "offer_hook",
    "product / service":       "product_category",
    "product/service":         "product_category",
    "product type":            "product_category",
    "product category":        "product_category",
    "service type":            "product_category",
    "product":                 "product_category",
    "category":                "product_category",
}


def _extract_brief_fields(text: str) -> dict[str, str]:
    """
    Extract brief key→value pairs from any block of text.
    Handles inline values, multi-line bullet lists, and bold markdown labels.
    """
    def _clean(s: str) -> str:
        return s.replace("**", "").replace("*", "").replace("__", "").strip()

    def _match_key(label: str) -> str | None:
        label_l = label.lower()
        best_key, best_len = None, 0
        for pattern, key in _BRIEF_LABEL_MAP.items():
            if pattern in label_l and len(pattern) > best_len:
                best_key, best_len = key, len(pattern)
        return best_key

    current_key: str | None = None
    value_parts: list[str] = []
    found: dict[str, str] = {}

    def _flush():
        if current_key and value_parts:
            val = " / ".join(p for p in value_parts if p)
            if val:
                found[current_key] = val

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        clean = _clean(stripped.lstrip("-•*#1234567890. "))
        if ":" in clean:
            label_raw, _, value_raw = clean.partition(":")
            label_clean = _clean(label_raw)
            value_clean = _clean(value_raw).strip()
            key = _match_key(label_clean)
            if key:
                _flush()
                current_key = key
                value_parts = [value_clean] if value_clean else []
                continue
        if current_key:
            cont = _clean(stripped.lstrip("-•*# "))
            if cont:
                value_parts.append(cont)

    _flush()
    return found


def _has_brief_content(text: str, min_fields: int = 4) -> bool:
    """Return True if text contains at least min_fields recognisable brief labels."""
    return len(_extract_brief_fields(text)) >= min_fields


def _brief_heading_start(content: str) -> int:
    """Return index of the first known brief heading in content, or -1."""
    cl = content.lower()
    start = -1
    for marker in _BRIEF_HEADINGS:
        pos = cl.find(marker)
        if pos != -1 and (start == -1 or pos < start):
            start = pos
    return start


def _has_brief_data(content: str) -> bool:
    """True if content has enough structured brief fields to show the save-prompt card."""
    start = _brief_heading_start(content)
    text = content[start:] if start != -1 else content
    min_fields = 2 if start != -1 else 4
    return len(_extract_brief_fields(text)) >= min_fields


def _save_brief_fields(content: str, project) -> int:
    """
    Save ANY brief fields found in content to the project. No minimum threshold.
    Returns the number of fields saved (0 if none found).
    Used for explicit user save requests.
    """
    start = _brief_heading_start(content)
    text_to_parse = content[start:] if start != -1 else content
    found = _extract_brief_fields(text_to_parse)
    if not found:
        return 0
    try:
        existing = _json.loads(project.marketing_brief or "{}")
    except Exception:
        existing = {}
    existing.update(found)
    project.marketing_brief = _json.dumps(existing)
    _update_project(project)
    return len(found)


def _parse_brief_from_ai(content: str, project) -> bool:
    """
    Parse brief data from AI text and save to project.
    - With a known heading: saves if 2+ fields found.
    - Without a heading: saves only if 4+ fields found (avoids false positives).
    Returns True if anything was saved.
    """
    start = _brief_heading_start(content)
    text_to_parse = content[start:] if start != -1 else content
    min_fields = 2 if start != -1 else 4

    found = _extract_brief_fields(text_to_parse)

    if len(found) < min_fields:
        return False

    try:
        existing = _json.loads(project.marketing_brief or "{}")
    except Exception:
        existing = {}

    existing.update(found)
    project.marketing_brief = _json.dumps(existing)
    _update_project(project)
    return True


def _detect_promo_intent(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _PROMO_KEYWORDS)


def _detect_brief_fill_intent(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _BRIEF_FILL_KEYWORDS)


def _brief_is_filled(brief_json: str) -> bool:
    try:
        brief = _json.loads(brief_json or "{}")
        return sum(1 for v in brief.values() if v and str(v).strip()) >= 3
    except Exception:
        return False


_SAVE_BRIEF_KEYWORDS = (
    "fill out the brief", "fill in the brief", "fill the brief",
    "save to brief", "save to the brief", "save it to the brief",
    "save this to the brief", "put this in the brief", "put it in the brief",
    "add to the brief", "update the brief page", "fill out the brief page",
    "save to brief page", "write it to the brief", "store in the brief",
)


def _detect_save_brief_intent(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _SAVE_BRIEF_KEYWORDS)


_PROJECT_DESC_KEYWORDS = (
    "my product", "my store", "my app", "my brand", "my business", "my company",
    "my service", "my shop", "my startup", "my website", "my saas",
    "we sell", "i sell", "our product", "our service", "our brand", "our store",
    "i'm selling", "i am selling", "i'm building", "i am building",
    "i'm launching", "i am launching", "i create", "we create", "i offer", "we offer",
    "i make", "we make", "our company", "our app", "our shop",
)


def _detect_project_desc_info(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _PROJECT_DESC_KEYWORDS)


def _description_needs_update(description: str, new_text: str) -> bool:
    """Return True if new_text likely contains info not reflected in description."""
    desc = (description or "").strip()
    if len(desc) < 30:
        return True
    # Check how many meaningful words from new_text are absent from description
    desc_words = set(desc.lower().split())
    new_words = [w.strip(".,!?") for w in new_text.lower().split() if len(w) > 4]
    new_unique = [w for w in new_words if w not in desc_words]
    return len(new_unique) >= 4


_GENERATION_TYPES = [
    ("chat",          ft.Icons.CHAT_BUBBLE_OUTLINE,     "Chat",          "Free-form AI conversation"),
    ("ad_copy",       ft.Icons.TEXT_FIELDS,              "Ad Copy",       "Generate ad headlines & copy"),
    ("image_prompt",  ft.Icons.IMAGE_OUTLINED,           "Image Prompt",  "Prompts for AI image generators"),
    ("video_prompt",  ft.Icons.MOVIE_OUTLINED,           "Video Prompt",  "Prompts for AI video generators"),
    ("bulk",          ft.Icons.FORMAT_LIST_BULLETED,     "10 Variations", "Generate 10 ad variations"),
    ("product_ideas", ft.Icons.LIGHTBULB_OUTLINE,        "Product Ideas", "Marketing angles & ideas"),
    ("local_image",   ft.Icons.AUTO_AWESOME,             "Local Image",   "Generate image locally with FLUX / SD"),
]


class ChatView:
    def __init__(self, page: ft.Page, app: "AppLayout"):
        self.page = page
        self.app = app
        self.state: AppState = app.state

        self._message_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            auto_scroll=True,
        )
        self._input_field: ft.TextField | None = None
        self._send_btn: ft.IconButton | None = None
        self._typing_indicator: ft.Container | None = None
        self._last_ai_content: str = ""
        self._chat_title_text: ft.Text | None = None
        self._model_dropdown: ft.Dropdown | None = None
        self._provider_dropdown: ft.Dropdown | None = None
        self._gen_type_row: ft.Row | None = None
        self._root: ft.Column | None = None
        self._pending_attachments: list[dict] = []
        self._attachment_row: ft.Row | None = None
        self._file_picker: ft.FilePicker | None = None
        self._attach_btn: ft.IconButton | None = None
        self._cost_label: ft.Text | None = None
        self._local_img_model_dd: ft.Dropdown | None = None
        self._local_img_model_row: ft.Container | None = None
        self._img_progress_text: ft.Text | None = None
        self._img_stop_btn: ft.IconButton | None = None
        self._gen_stop_event: threading.Event | None = None
        self._vision_supported: bool = True  # cached; updated in background

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Column:
        self._file_picker = ft.FilePicker(on_result=self._on_files_picked)
        self.page.overlay.append(self._file_picker)
        self._refresh_vision_cache()

        self._chat_title_text = ft.Text(
            self._current_chat_title(),
            size=14,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
        )
        self._img_progress_text = ft.Text(
            "", size=11, color=T.ACCENT_LIGHT, visible=False, font_family="monospace"
        )
        self._img_stop_btn = ft.IconButton(
            icon=ft.Icons.STOP_CIRCLE_OUTLINED,
            icon_size=16,
            icon_color=T.ERROR,
            tooltip="Stop generation",
            visible=False,
            on_click=self._stop_generation,
        )
        self._typing_indicator = ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=T.ACCENT),
                    ft.Text("Generating…", size=12, color=T.TEXT_MUTED),
                    self._img_progress_text,
                    self._img_stop_btn,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=6),
            visible=False,
        )

        self._root = ft.Column(
            controls=[
                self._header(),
                self._gen_type_selector(),
                self._local_img_bar(),
                T.divider(),
                self._message_list,
                self._typing_indicator,
                T.divider(),
                self._input_area(),
            ],
            spacing=0,
            expand=True,
        )
        self.reload_messages()
        return self._root

    # ── Sub-sections ──────────────────────────────────────────────────────────

    def _header(self) -> ft.Container:
        _provider_opts = [ft.dropdown.Option(p, p.capitalize()) for p in list_providers()]
        _provider_opts.append(ft.dropdown.Option("local", "Local"))
        self._provider_dropdown = ft.Dropdown(
            value=self.state.selected_provider,
            options=_provider_opts,
            on_change=self._on_provider_change,
            width=120,
            bgcolor=T.BG_CARD,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
        )
        models = get_models_for_provider(self.state.selected_provider)
        self._model_dropdown = ft.Dropdown(
            value=self.state.selected_model if self.state.selected_model in models else models[0],
            options=[ft.dropdown.Option(m) for m in models],
            on_change=self._on_model_change,
            width=190,
            bgcolor=T.BG_CARD,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=16, color=T.ACCENT_LIGHT),
                    self._chat_title_text,
                    T.icon_button(
                        ft.Icons.MANAGE_SEARCH,
                        "Chat History",
                        on_click=self._open_history,
                        color=T.TEXT_SECONDARY,
                    ),
                    ft.Container(expand=True),
                    self._provider_dropdown,
                    self._model_dropdown,
                    T.icon_button(
                        ft.Icons.ADD_COMMENT_OUTLINED,
                        "New Chat",
                        on_click=self._new_chat,
                        color=T.TEXT_SECONDARY,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=T.BG_SECONDARY,
        )

    def _gen_type_selector(self) -> ft.Container:
        buttons = []
        for gtype, icon, label, tooltip in _GENERATION_TYPES:
            is_active = self.state.generation_type == gtype
            btn = ft.Container(
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
                tooltip=tooltip,
                on_click=lambda e, g=gtype: self._set_gen_type(g),
                ink=True,
            )
            buttons.append(btn)

        self._gen_type_row = ft.Row(controls=buttons, spacing=6, scroll=ft.ScrollMode.AUTO)
        return ft.Container(
            content=self._gen_type_row,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=T.BG_SECONDARY,
        )

    def _local_img_bar(self) -> ft.Container:
        """Compact model + aspect-ratio picker shown only when Local Image is active."""
        from ai_providers.local_image_provider import get_installed_models, IMAGE_CATALOG_BY_ID
        from storage.settings_repo import get_setting

        installed = get_installed_models()
        is_active = self.state.generation_type == "local_image"

        if not installed:
            inner = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=13, color=T.TEXT_MUTED),
                    ft.Text("No local models installed.", size=11, color=T.TEXT_MUTED),
                    ft.TextButton(
                        "Open Settings →",
                        on_click=lambda e: self.app.show_settings_view(),
                        style=ft.ButtonStyle(
                            color=T.ACCENT_LIGHT,
                            padding=ft.padding.symmetric(horizontal=4, vertical=0),
                        ),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self._local_img_model_dd = None
        else:
            saved = get_setting("imggen_model", "")
            default = saved if saved in installed else installed[0]

            self._local_img_model_dd = ft.Dropdown(
                value=default,
                options=[
                    ft.dropdown.Option(
                        key=mid,
                        text=IMAGE_CATALOG_BY_ID.get(mid, {}).get("label", mid),
                    )
                    for mid in installed
                ],
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                text_size=12,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=4),
                border_radius=8,
                width=210,
                on_change=lambda e: self._update_cost_label(
                    self._input_field.value or ""
                ),
            )

            # Aspect ratio presets: label → (width, height)
            _AR = [
                ("1:1",  768,  768),
                ("16:9", 1280, 720),
                ("9:16", 720, 1280),
                ("4:3",  1024, 768),
                ("3:4",  768, 1024),
            ]
            saved_w = int(get_setting("imggen_width", "768"))
            saved_h = int(get_setting("imggen_height", "768"))

            def _ar_match(w, h):
                for lbl, aw, ah in _AR:
                    if aw == w and ah == h:
                        return lbl
                return "1:1"

            self._local_img_ar_dd = ft.Dropdown(
                value=_ar_match(saved_w, saved_h),
                options=[ft.dropdown.Option(key=lbl, text=lbl) for lbl, _, _ in _AR],
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                text_size=12,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=4),
                border_radius=8,
                width=80,
            )

            inner = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, size=13, color=T.ACCENT_LIGHT),
                    ft.Text("Model", size=11, color=T.TEXT_MUTED),
                    self._local_img_model_dd,
                    ft.Text("Size", size=11, color=T.TEXT_MUTED),
                    self._local_img_ar_dd,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        self._local_img_model_row = ft.Container(
            content=inner,
            padding=ft.padding.symmetric(horizontal=16, vertical=7),
            bgcolor=T.ACCENT_DIM,
            border=ft.border.only(bottom=ft.BorderSide(1, T.BORDER_ACCENT)),
            visible=is_active,
        )
        return self._local_img_model_row

    def _input_area(self) -> ft.Container:
        self._input_field = ft.TextField(
            hint_text="Type your message… (Shift+Enter for new line)",
            multiline=True,
            min_lines=1,
            max_lines=6,
            expand=True,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=T.TEXT_MUTED),
            cursor_color=T.ACCENT_LIGHT,
            border_radius=10,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            on_submit=self._on_send,
            on_change=self._on_input_change,
            shift_enter=True,
        )
        self._send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            tooltip="Send (Enter)",
            on_click=self._on_send,
            icon_color=T.ACCENT_LIGHT,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor={"": T.ACCENT_DIM, "hovered": T.ACCENT},
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=10, vertical=10),
            ),
        )
        self._attach_btn = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE,
            tooltip=self._attach_tooltip(),
            on_click=self._open_file_picker,
            icon_color=T.TEXT_MUTED,
            icon_size=20,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=10),
            ),
        )
        attach_btn = self._attach_btn
        self._attachment_row = ft.Row(
            controls=[],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.START,
            visible=False,
            height=96,
        )
        self._cost_label = ft.Text(
            "",
            size=10,
            color=T.TEXT_MUTED,
            visible=False,
        )
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._attachment_row,
                    ft.Row(
                        controls=[attach_btn, self._input_field, self._send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Row(
                        controls=[ft.Container(expand=True), self._cost_label],
                        spacing=0,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            bgcolor=T.BG_SECONDARY,
        )

    # ── Message rendering ─────────────────────────────────────────────────────

    def reload_messages(self) -> None:
        """Clear and reload messages for the current chat."""
        self._message_list.controls.clear()
        if not self.state.current_chat:
            self._message_list.controls.append(self._empty_state())
        else:
            messages = chat_repo.get_messages(self.state.current_chat.id)
            if not messages:
                self._message_list.controls.append(self._empty_state())
            for msg in messages:
                self._message_list.controls.append(self._make_bubble(msg))
        try:
            self._message_list.update()
        except Exception:
            pass

    def _empty_state(self) -> ft.Container:
        project_name = self.state.current_project.name if self.state.current_project else "a project"
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Text("✦", size=36, color=T.ACCENT_LIGHT),
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(
                        f"Start a conversation for {project_name}",
                        size=16,
                        color=T.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        "Choose a generation type above, then type your message.",
                        size=13,
                        color=T.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Row(
                        controls=[
                            self._quick_prompt_chip("Write 3 Facebook ad headlines"),
                            self._quick_prompt_chip("Generate 5 product descriptions"),
                            self._quick_prompt_chip("Create an image prompt for a lifestyle photo"),
                        ],
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            expand=True,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=40, vertical=40),
        )

    def _quick_prompt_chip(self, text: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=12, color=T.TEXT_ACCENT),
            padding=ft.padding.symmetric(horizontal=12, vertical=7),
            bgcolor=T.ACCENT_DIM,
            border=ft.border.all(1, T.BORDER_ACCENT),
            border_radius=20,
            on_click=lambda e, t=text: self._inject_prompt(t),
            ink=True,
        )

    def _make_bubble(self, msg: Message) -> ft.Container:
        is_user = msg.role == "user"

        # Detect local image messages
        img_data = None
        if not is_user:
            try:
                parsed = _json.loads(msg.content)
                if parsed.get("__type") == "local_image":
                    img_data = parsed
            except Exception:
                pass

        # Message text / image control
        if img_data:
            text_control = self._make_image_content(img_data)
        elif not is_user:
            text_control = ft.SelectionArea(
                content=ft.Markdown(
                    msg.content,
                    selectable=False,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme="atom-one-dark",
                    on_tap_link=lambda e: self.page.launch_url(e.data),
                )
            )
        else:
            text_control = ft.Text(
                msg.content,
                size=13,
                color=T.TEXT_PRIMARY,
                selectable=True,
            )

        # Footer for AI messages
        footer_controls = []
        if not is_user and (msg.model or msg.tokens_used):
            footer_controls.append(
                ft.Row(
                    controls=[
                        T.provider_badge(msg.provider) if msg.provider else ft.Container(),
                        ft.Text(msg.model, size=10, color=T.TEXT_MUTED),
                        ft.Text(f"·  {msg.tokens_used} tokens", size=10, color=T.TEXT_MUTED) if msg.tokens_used else ft.Container(),
                        ft.Text(f"·  ${msg.cost:.5f}", size=10, color=T.TEXT_MUTED) if msg.cost else ft.Container(),
                    ],
                    spacing=6,
                )
            )

        # Action buttons for AI messages
        action_row = ft.Row(spacing=2) if not is_user else None
        if action_row is not None:
            action_row.controls = [
                T.icon_button(
                    ft.Icons.CONTENT_COPY_OUTLINED,
                    "Copy",
                    on_click=lambda e, c=msg.content: self._copy_to_clipboard(c),
                    size=15,
                ),
                T.icon_button(
                    ft.Icons.BOOKMARK_BORDER,
                    "Save to Assets",
                    on_click=lambda e, m=msg: self._save_as_asset(m),
                    size=15,
                ),
                T.icon_button(
                    ft.Icons.PUSH_PIN_OUTLINED,
                    "Pin message",
                    on_click=lambda e, m=msg: self._pin_message(m),
                    size=15,
                ),
            ]
            # Show "Save to Brief" button when the message contains recognisable brief data
            if _has_brief_content(msg.content):
                action_row.controls.append(
                    T.icon_button(
                        ft.Icons.ASSIGNMENT_OUTLINED,
                        "Save to Brief",
                        on_click=lambda e, c=msg.content: self._save_content_to_brief(c),
                        size=15,
                    )
                )

        bubble_content_controls = [text_control]
        if footer_controls:
            bubble_content_controls.append(ft.Container(height=6))
            bubble_content_controls.extend(footer_controls)
        if action_row is not None:
            bubble_content_controls.append(action_row)

        bubble = ft.Container(
            content=ft.Column(controls=bubble_content_controls, spacing=4, tight=True),
            bgcolor=T.BG_USER_MSG if is_user else T.BG_AI_MSG,
            border_radius=ft.border_radius.only(
                top_left=12,
                top_right=12,
                bottom_left=2 if is_user else 12,
                bottom_right=12 if is_user else 2,
            ),
            border=ft.border.all(1, T.BORDER),
            padding=ft.padding.symmetric(horizontal=12, vertical=12),
            # Cap width to avoid ultra-wide bubbles
        )

        # Avatar
        avatar = ft.Container(
            content=ft.Text(
                "YOU" if is_user else "AI",
                size=9,
                weight=ft.FontWeight.BOLD,
                color=T.TEXT_PRIMARY,
            ),
            width=32,
            height=32,
            bgcolor=T.ACCENT if is_user else T.ACCENT_DIM,
            border_radius=16,
            alignment=ft.alignment.center,
        )

        if is_user:
            row_controls = [ft.Container(expand=True), bubble, avatar]
        else:
            bubble.expand = True
            row_controls = [avatar, bubble]

        return ft.Row(
            controls=row_controls,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_send(self, e) -> None:
        text = self._input_field.value.strip() if self._input_field else ""
        has_attachments = bool(self._pending_attachments)
        if not text and not has_attachments:
            return
        if self.state.is_generating:
            return

        project = self.state.current_project

        # Save brief intent — parse last AI response directly, no new AI call
        if _detect_save_brief_intent(text):
            if not project:
                self._snack("Select a project first", error=True)
                return
            if not self._last_ai_content:
                self._snack("No AI response to save yet. Chat first or go to the Brief page.", error=True)
                if self._input_field:
                    self._input_field.value = ""
                    self._input_field.update()
                return
            n = _save_brief_fields(self._last_ai_content, project)
            if n > 0:
                fresh = _get_project(project.id)
                if fresh:
                    self.state.current_project = fresh
                self.app.refresh_brief_if_active()
                self._snack(f"Saved {n} field{'s' if n != 1 else ''} to Brief ✓  —  Check the Brief page")
            else:
                self._snack(
                    "No brief fields found in my last response. "
                    "Say 'help me fill my brief' to start the interview.",
                    error=True,
                )
            if self._input_field:
                self._input_field.value = ""
                self._input_field.update()
            return

        # Fill-brief intent — start the guided interview
        if _detect_brief_fill_intent(text):
            self._dispatch(_BRIEF_FILL_API_TEXT, display_text=text)
            return

        if (
            project
            and _detect_promo_intent(text)
            and not _brief_is_filled(project.marketing_brief)
        ):
            attachments = list(self._pending_attachments)
            self._pending_attachments.clear()
            self._refresh_attachment_row()
            self._show_marketing_brief_dialog(text, attachments=attachments)
            return

        if self.state.generation_type == "local_image":
            if self._input_field:
                self._input_field.value = ""
                self._input_field.update()
            self._dispatch_image(text)
            return

        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()
        self._refresh_attachment_row()
        self._dispatch(text, attachments=attachments)

    def _show_marketing_brief_dialog(self, pending_text: str, attachments: list[dict] | None = None) -> None:
        project = self.state.current_project
        if not project:
            return

        try:
            existing = _json.loads(project.marketing_brief or "{}")
        except Exception:
            existing = {}

        field_refs: dict[str, ft.TextField] = {}
        field_controls: list[ft.Control] = []
        for key, label, hint, multiline in _BRIEF_FIELDS:
            tf = ft.TextField(
                label=label,
                hint_text=hint,
                value=existing.get(key, ""),
                multiline=multiline,
                min_lines=1,
                max_lines=3 if multiline else 1,
                bgcolor=T.BG_INPUT,
                border_color=T.BORDER,
                focused_border_color=T.ACCENT,
                color=T.TEXT_PRIMARY,
                label_style=ft.TextStyle(color=T.TEXT_MUTED, size=12),
                hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
                cursor_color=T.ACCENT_LIGHT,
                border_radius=8,
                text_size=12,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
            )
            field_refs[key] = tf
            field_controls.append(tf)

        dlg = ft.AlertDialog(modal=True)

        def on_save(e):
            dlg.open = False
            brief_data = {k: (tf.value or "").strip() for k, tf in field_refs.items()}
            project.marketing_brief = _json.dumps(brief_data)
            _update_project(project)
            self.page.update()
            self._dispatch(pending_text, attachments=attachments)

        def on_skip(e):
            dlg.open = False
            self.page.update()
            self._dispatch(pending_text, attachments=attachments)

        dlg.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.CAMPAIGN_OUTLINED, color=T.ACCENT_LIGHT, size=20),
                ft.Text(
                    "Marketing Brief",
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=T.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                ft.Text(
                    f"Project: {project.name}",
                    size=11,
                    color=T.TEXT_MUTED,
                ),
            ],
            spacing=8,
        )
        dlg.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Fill in your marketing brief so the AI generates highly targeted content. "
                        "This is saved as a preset for this project.",
                        size=12,
                        color=T.TEXT_MUTED,
                    ),
                    ft.Container(height=6),
                    *field_controls,
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=560,
            height=500,
            padding=ft.padding.only(top=4),
        )
        dlg.bgcolor = T.BG_SECONDARY
        dlg.actions = [
            ft.TextButton(
                "Skip for now",
                on_click=on_skip,
                style=ft.ButtonStyle(color=T.TEXT_MUTED),
            ),
            ft.FilledButton(
                "Save & Send",
                on_click=on_save,
                style=ft.ButtonStyle(bgcolor={"": T.ACCENT}),
            ),
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.END

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _dispatch_image(self, prompt: str) -> None:
        """Generate an image locally in a background thread."""
        self.state.is_generating = True
        self._input_field.value = ""
        self._input_field.disabled = True
        self._send_btn.disabled = True
        self._typing_indicator.visible = True

        # Reset stop event and show progress/stop controls
        self._gen_stop_event = threading.Event()
        if self._img_progress_text:
            self._img_progress_text.value = ""
            self._img_progress_text.visible = True
        if self._img_stop_btn:
            self._img_stop_btn.visible = True

        self._message_list.controls = [
            c for c in self._message_list.controls
            if not isinstance(c, ft.Container) or not _is_empty_state(c)
        ]

        user_msg = Message(id="temp", chat_id="", role="user", content=prompt)
        self._message_list.controls.append(self._make_bubble(user_msg))
        self.page.update()

        # Capture dropdown values on the UI thread before the background thread runs
        _selected_model = (
            self._local_img_model_dd.value
            if self._local_img_model_dd and self._local_img_model_dd.value
            else None
        )
        # Also allow selecting from header model dropdown when provider is "local"
        if not _selected_model and self._provider_dropdown and self._provider_dropdown.value == "local":
            _selected_model = self._model_dropdown.value if self._model_dropdown else None

        _AR_MAP = {
            "1:1":  (768,  768),
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3":  (1024, 768),
            "3:4":  (768, 1024),
        }
        _ar_val = getattr(self, "_local_img_ar_dd", None)
        _ar_key = _ar_val.value if _ar_val and _ar_val.value else "1:1"
        _sel_w, _sel_h = _AR_MAP.get(_ar_key, (768, 768))
        _stop_ev = self._gen_stop_event

        def _on_progress(msg: str):
            if self._img_progress_text:
                self._img_progress_text.value = msg
                try:
                    self._img_progress_text.update()
                except Exception:
                    pass

        def run():
            try:
                from ai_providers.local_image_provider import generate_image, get_imggen_settings
                cfg = get_imggen_settings()

                result = generate_image(
                    prompt=prompt,
                    model_id=_selected_model or cfg["model_id"] or None,
                    width=_sel_w,
                    height=_sel_h,
                    steps=cfg["steps"],
                    cfg=cfg["cfg"],
                    on_progress=_on_progress,
                    stop_event=_stop_ev,
                )

                if result.get("error") == "Cancelled":
                    self._message_list.controls.append(
                        self._error_bubble("Generation stopped.")
                    )
                    self.page.update()
                    return

                if not self.state.current_chat:
                    from storage.chat_repo import create_chat
                    project_id = self.state.current_project.id if self.state.current_project else None
                    self.state.current_chat = create_chat(project_id=project_id)
                    self.state.refresh_chats()

                from storage.chat_repo import add_message as _add_msg
                _add_msg(chat_id=self.state.current_chat.id, role="user", content=prompt)

                if result["ok"]:
                    img_content = _json.dumps({
                        "__type":  "local_image",
                        "path":    result["path"],
                        "prompt":  prompt,
                        "backend": result.get("backend", ""),
                    })
                    used_model = result.get("model") or cfg["model_id"] or "local"
                    _add_msg(
                        chat_id=self.state.current_chat.id,
                        role="assistant",
                        content=img_content,
                        provider="local",
                        model=used_model,
                    )
                    ai_msg = Message(
                        id="temp_ai",
                        chat_id=self.state.current_chat.id,
                        role="assistant",
                        content=img_content,
                        provider="local",
                        model=used_model,
                    )
                    self._message_list.controls.append(self._make_bubble(ai_msg))
                    self._schedule_ai_title(prompt, f"[Image generated: {prompt[:60]}]")
                    if self.state.current_project:
                        asset_repo.save_asset(
                            project_id=self.state.current_project.id,
                            asset_type="image",
                            content=result["path"],
                            title=prompt[:80],
                            provider=result.get("backend", "local"),
                            model=used_model,
                        )
                else:
                    self._message_list.controls.append(self._error_bubble(result["error"]))

                self.state.refresh_chats()
                self.app.refresh_right_panel()
            except Exception as exc:
                self._message_list.controls.append(self._error_bubble(str(exc)))
            finally:
                self.state.is_generating = False
                self._input_field.disabled = False
                self._send_btn.disabled = False
                self._typing_indicator.visible = False
                if self._img_progress_text:
                    self._img_progress_text.visible = False
                if self._img_stop_btn:
                    self._img_stop_btn.visible = False
                self._gen_stop_event = None
                self.page.update()

        threading.Thread(target=run, daemon=True).start()

    def _dispatch(
        self,
        text: str,
        display_text: str | None = None,
        attachments: list[dict] | None = None,
    ) -> None:
        """Send message to AI in a background thread.

        display_text overrides what appears in the bubble (e.g. when text has an injected instruction).
        attachments is a list of processed file dicts from core.file_handler.
        """
        self.state.is_generating = True
        self._input_field.value = ""
        self._input_field.disabled = True
        self._send_btn.disabled = True
        self._typing_indicator.visible = True

        # Remove empty state if present
        self._message_list.controls = [
            c for c in self._message_list.controls
            if not isinstance(c, ft.Container) or not _is_empty_state(c)
        ]

        # Build display text — append file names so user sees what was attached
        bubble_text = display_text if display_text is not None else text
        if attachments:
            names = " · ".join(a["filename"] for a in attachments)
            bubble_text = f"{bubble_text}\n\n📎 {names}" if bubble_text.strip() else f"📎 {names}"

        # Optimistic user bubble
        user_msg = Message(
            id="temp",
            chat_id="",
            role="user",
            content=bubble_text,
        )
        self._message_list.controls.append(self._make_bubble(user_msg))
        self.page.update()

        def run():
            try:
                images = [a for a in (attachments or []) if a["type"] == "image"]
                file_context = "\n\n".join(
                    f"### {a['filename']}\n{a['text']}"
                    for a in (attachments or [])
                    if a["type"] in ("document", "text", "video") and a.get("text")
                )
                result = dispatcher.generate(
                    state=self.state,
                    user_input=text,
                    file_context=file_context,
                    images=images,
                )

                if result.ok:
                    self._last_ai_content = result.content
                    ai_msg = Message(
                        id="temp_ai",
                        chat_id=self.state.current_chat.id if self.state.current_chat else "",
                        role="assistant",
                        content=result.content,
                        provider=result.provider,
                        model=result.model,
                        tokens_used=result.tokens_input + result.tokens_output,
                        cost=result.cost,
                    )
                    self._message_list.controls.append(self._make_bubble(ai_msg))
                    self._schedule_ai_title(display_text or text, result.content)

                    project = self.state.current_project
                    brief_has_data = project and _has_brief_data(result.content)
                    brief_parsed = False
                    if brief_has_data:
                        # AI generated structured brief data — ask user to save
                        self._show_brief_save_suggestion(result.content)
                        brief_parsed = True  # suppress description suggestion

                    # Suggest updating project description when user describes their product
                    user_text = display_text if display_text is not None else text
                    if (
                        not brief_parsed
                        and project
                        and len(user_text) >= 15
                        and _detect_project_desc_info(user_text)
                        and _description_needs_update(project.description, user_text)
                    ):
                        self._show_description_suggestion(user_text)
                else:
                    self._message_list.controls.append(self._error_bubble(result.error or "Unknown error"))

                self.state.refresh_chats()
                self.app.refresh_right_panel()
            except Exception as exc:
                self._message_list.controls.append(self._error_bubble(str(exc)))
            finally:
                self.state.is_generating = False
                self._input_field.disabled = False
                self._send_btn.disabled = False
                self._typing_indicator.visible = False
                self.page.update()

        threading.Thread(target=run, daemon=True).start()

    # ── File attachment helpers ───────────────────────────────────────────────

    # ── Vision / attach-button helpers ───────────────────────────────────────

    def _current_supports_vision(self) -> bool:
        return self._vision_supported

    def _refresh_vision_cache(self) -> None:
        """Re-compute vision support off the UI thread; update button when done."""
        provider_name = self.state.selected_provider
        model_name    = self.state.selected_model

        def run():
            from ai_providers.router import get_provider
            try:
                result = get_provider(provider_name).supports_vision(model_name)
            except Exception:
                result = False
            self._vision_supported = result
            self._update_attach_btn()

        threading.Thread(target=run, daemon=True).start()

    def _attach_tooltip(self) -> str:
        if self._vision_supported:
            return "Attach file (image, PDF, Word, Excel, video…)"
        return "Attach document (PDF, Word, Excel, CSV, TXT) — images require a vision model"

    def _update_attach_btn(self) -> None:
        if not self._attach_btn:
            return
        self._attach_btn.tooltip = self._attach_tooltip()
        try:
            self._attach_btn.update()
        except Exception:
            pass

    def _open_file_picker(self, e) -> None:
        if not self._file_picker:
            return
        doc_exts = ["pdf", "docx", "doc", "xlsx", "xls", "csv", "txt", "md"]
        if self._current_supports_vision():
            extensions = (
                ["jpg", "jpeg", "png", "gif", "webp", "bmp"]
                + doc_exts
                + ["mp4", "mov", "avi", "mkv", "webm"]
            )
        else:
            extensions = doc_exts
        self._file_picker.pick_files(
            dialog_title="Attach files",
            allow_multiple=True,
            allowed_extensions=extensions,
        )

    def _on_files_picked(self, e) -> None:
        if not e.files:
            return
        from core.file_handler import process_file
        for f in e.files:
            if f.path:
                try:
                    attachment = process_file(f.path)
                    attachment["file_path"] = f.path  # keep for thumbnail rendering
                    self._pending_attachments.append(attachment)
                except Exception as exc:
                    self._snack(f"Could not read {f.name}: {exc}", error=True)
        self._refresh_attachment_row()

    def _remove_attachment(self, idx: int) -> None:
        if 0 <= idx < len(self._pending_attachments):
            self._pending_attachments.pop(idx)
        self._refresh_attachment_row()

    def _refresh_attachment_row(self) -> None:
        if not self._attachment_row:
            return
        self._attachment_row.controls.clear()
        for i, att in enumerate(self._pending_attachments):
            self._attachment_row.controls.append(self._make_attachment_preview(att, i))
        self._attachment_row.visible = bool(self._pending_attachments)
        try:
            self._attachment_row.update()
        except Exception:
            pass

    def _make_attachment_preview(self, att: dict, idx: int) -> ft.Control:
        """Rich preview card for an attachment — image thumb, video card, or doc card."""

        def _remove_btn(i: int) -> ft.Container:
            return ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=10,
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda e, n=i: self._remove_attachment(n),
                    style=ft.ButtonStyle(
                        bgcolor={"": "#99000000"},
                        shape=ft.CircleBorder(),
                        padding=ft.padding.all(2),
                    ),
                    width=20,
                    height=20,
                ),
                top=4,
                right=4,
            )

        if att["type"] == "image":
            return ft.Stack(
                controls=[
                    ft.Container(
                        content=ft.Image(
                            src=att.get("file_path", ""),
                            width=88,
                            height=88,
                            fit=ft.ImageFit.COVER,
                            border_radius=8,
                        ),
                        width=88,
                        height=88,
                        border_radius=8,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        border=ft.border.all(1, T.BORDER),
                    ),
                    _remove_btn(idx),
                ],
                width=88,
                height=88,
            )

        if att["type"] == "video":
            ext = att["filename"].rsplit(".", 1)[-1].upper() if "." in att["filename"] else "VIDEO"
            return ft.Stack(
                controls=[
                    ft.Container(
                        width=120,
                        height=88,
                        bgcolor=T.BG_CARD,
                        border_radius=8,
                        border=ft.border.all(1, T.BORDER),
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.PLAY_CIRCLE_OUTLINE,
                                        size=30,
                                        color=T.ACCENT_LIGHT,
                                    ),
                                    bgcolor="#1a1f35",
                                    width=120,
                                    height=54,
                                    alignment=ft.alignment.center,
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Container(
                                                content=ft.Text(
                                                    ext,
                                                    size=9,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=T.ACCENT_LIGHT,
                                                ),
                                                bgcolor=T.ACCENT_DIM,
                                                border_radius=3,
                                                padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                            ),
                                            ft.Text(
                                                att["filename"],
                                                size=10,
                                                color=T.TEXT_PRIMARY,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                expand=True,
                                            ),
                                        ],
                                        spacing=4,
                                        tight=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    padding=ft.padding.symmetric(horizontal=6, vertical=4),
                                ),
                            ],
                            spacing=0,
                            tight=True,
                        ),
                    ),
                    _remove_btn(idx),
                ],
                width=120,
                height=88,
            )

        # Document / text / unknown
        ext = att["filename"].rsplit(".", 1)[-1].upper() if "." in att["filename"] else "FILE"
        icon_map = {
            "document": ft.Icons.DESCRIPTION_OUTLINED,
            "text":     ft.Icons.CODE,
        }
        file_icon = icon_map.get(att["type"], ft.Icons.ATTACH_FILE)
        snippet = (att.get("text") or "").strip()[:55]
        if len(att.get("text", "")) > 55:
            snippet += "…"

        return ft.Stack(
            controls=[
                ft.Container(
                    width=160,
                    height=88,
                    bgcolor=T.BG_CARD,
                    border_radius=8,
                    border=ft.border.all(1, T.BORDER),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(file_icon, size=14, color=T.ACCENT_LIGHT),
                                    ft.Container(
                                        content=ft.Text(
                                            ext,
                                            size=9,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.ACCENT_LIGHT,
                                        ),
                                        bgcolor=T.ACCENT_DIM,
                                        border_radius=3,
                                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                    ),
                                ],
                                spacing=5,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                att["filename"],
                                size=11,
                                color=T.TEXT_PRIMARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                snippet if snippet else "No text preview",
                                size=9,
                                color=T.TEXT_MUTED,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                ),
                _remove_btn(idx),
            ],
            width=160,
            height=88,
        )

    def _open_image_fullscreen(self, path: str, prompt: str) -> None:
        dlg = ft.AlertDialog(modal=True, bgcolor=T.BG_SECONDARY)

        def _close(e):
            dlg.open = False
            self.page.update()

        dlg.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Image(
                        src=path,
                        fit=ft.ImageFit.CONTAIN,
                        expand=True,
                        border_radius=8,
                    ),
                    ft.Text(
                        prompt[:200] + ("…" if len(prompt) > 200 else ""),
                        size=11,
                        color=T.TEXT_MUTED,
                        italic=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                expand=True,
            ),
            width=800,
            height=700,
            padding=10,
        )
        dlg.actions = [
            ft.TextButton("Close", on_click=_close, style=ft.ButtonStyle(color=T.TEXT_MUTED)),
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.END
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _make_image_content(self, img_data: dict) -> ft.Column:
        """Render a locally generated image inside a chat bubble."""
        path    = img_data.get("path", "")
        prompt  = img_data.get("prompt", "")
        backend = img_data.get("backend", "local")

        backend_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.COMPUTER_OUTLINED, size=10, color=T.ACCENT_LIGHT),
                    ft.Text(backend or "local", size=9, weight=ft.FontWeight.BOLD, color=T.ACCENT_LIGHT),
                ],
                spacing=3,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=T.ACCENT_DIM,
            border=ft.border.all(1, T.BORDER_ACCENT),
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=5, vertical=2),
        )

        image_ctrl = ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap=lambda e, p=path, pr=prompt: self._open_image_fullscreen(p, pr),
            content=ft.Stack(
                controls=[
                    ft.Image(
                        src=path,
                        width=420,
                        height=420,
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=8,
                        error_content=ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, size=32, color=T.TEXT_MUTED),
                                    ft.Text(
                                        f"Image not found:\n{path}",
                                        size=11,
                                        color=T.TEXT_MUTED,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                            ),
                            width=420,
                            height=120,
                            alignment=ft.alignment.center,
                        ),
                    ),
                    ft.Container(
                        content=ft.Icon(ft.Icons.ZOOM_IN, size=20, color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
                        border_radius=20,
                        padding=6,
                        right=8,
                        bottom=8,
                    ),
                ],
                width=420,
                height=420,
            ),
        )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[backend_badge],
                    spacing=4,
                ),
                image_ctrl,
                ft.Text(
                    prompt[:120] + ("…" if len(prompt) > 120 else ""),
                    size=11,
                    color=T.TEXT_MUTED,
                    italic=True,
                ),
            ],
            spacing=6,
            tight=True,
        )

    def _error_bubble(self, message: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=T.ERROR, size=16),
                    ft.Text(message, color=T.ERROR, size=12, expand=True),
                ],
                spacing=8,
            ),
            bgcolor="#2d0a0a",
            border=ft.border.all(1, T.ERROR),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=12),
        )

    def _on_input_change(self, e) -> None:
        self._update_cost_label(e.control.value or "")

    def _update_cost_label(self, text: str) -> None:
        if not self._cost_label:
            return
        if self.state.generation_type == "local_image":
            if self._local_img_model_dd and self._local_img_model_dd.value:
                from ai_providers.local_image_provider import IMAGE_CATALOG_BY_ID
                entry = IMAGE_CATALOG_BY_ID.get(self._local_img_model_dd.value, {})
                model_label = entry.get("label", self._local_img_model_dd.value)
                self._cost_label.value = f"free · {model_label}"
            else:
                self._cost_label.value = "free (local)"
            self._cost_label.visible = bool(text.strip())
            try:
                self._cost_label.update()
            except Exception:
                pass
            return
        stripped = text.strip()
        if not stripped:
            self._cost_label.visible = False
            try:
                self._cost_label.update()
            except Exception:
                pass
            return

        from core.prompt_builder import estimate_token_count
        from ai_providers.router import get_provider as _get_prov
        tokens = estimate_token_count(stripped)
        provider_name = self.state.selected_provider
        model = self.state.selected_model
        try:
            prov = _get_prov(provider_name)
            if provider_name == "ollama":
                label = f"~{tokens:,} tokens · free (local)"
            else:
                cost = prov.estimate_cost(tokens, model)
                if cost < 0.000005:
                    label = f"~{tokens:,} tokens · <$0.00001"
                else:
                    label = f"~{tokens:,} tokens · ~${cost:.5f}"
        except Exception:
            label = f"~{tokens:,} tokens"

        self._cost_label.value = label
        self._cost_label.visible = True
        try:
            self._cost_label.update()
        except Exception:
            pass

    def _on_provider_change(self, e) -> None:
        provider = e.control.value
        if provider == "local":
            from ai_providers.local_image_provider import get_installed_models, IMAGE_CATALOG_BY_ID
            installed = get_installed_models()
            if self._model_dropdown:
                if installed:
                    self._model_dropdown.options = [
                        ft.dropdown.Option(mid, IMAGE_CATALOG_BY_ID[mid]["label"])
                        for mid in installed if mid in IMAGE_CATALOG_BY_ID
                    ]
                    self._model_dropdown.value = installed[0]
                    if self._local_img_model_dd:
                        self._local_img_model_dd.value = installed[0]
                        try:
                            self._local_img_model_dd.update()
                        except Exception:
                            pass
                else:
                    self._model_dropdown.options = [ft.dropdown.Option("", "No models installed")]
                    self._model_dropdown.value = ""
                self._model_dropdown.update()
            self._set_gen_type("local_image")
            return
        self.state.selected_provider = provider
        models = get_models_for_provider(self.state.selected_provider)
        self.state.selected_model = models[0] if models else ""
        if self._model_dropdown:
            self._model_dropdown.options = [ft.dropdown.Option(m) for m in models]
            self._model_dropdown.value = self.state.selected_model
            self._model_dropdown.update()
        _save_default(self.state.selected_provider, self.state.selected_model)
        self._refresh_vision_cache()
        self._update_cost_label(self._input_field.value if self._input_field else "")
        self.app.refresh_right_panel()

    def _on_model_change(self, e) -> None:
        if self._provider_dropdown and self._provider_dropdown.value == "local":
            if self._local_img_model_dd:
                self._local_img_model_dd.value = e.control.value
                try:
                    self._local_img_model_dd.update()
                except Exception:
                    pass
            return
        self.state.selected_model = e.control.value
        _save_default(self.state.selected_provider, self.state.selected_model)
        self._refresh_vision_cache()
        self._update_cost_label(self._input_field.value if self._input_field else "")
        self.app.refresh_right_panel()

    def _stop_generation(self, e=None) -> None:
        if self._gen_stop_event:
            self._gen_stop_event.set()

    def _set_gen_type(self, gtype: str) -> None:
        self.state.generation_type = gtype
        self._rebuild_gen_type_row()
        if self._local_img_model_row:
            self._local_img_model_row.visible = (gtype == "local_image")
            try:
                self._local_img_model_row.update()
            except Exception:
                pass
        self._update_cost_label(self._input_field.value if self._input_field else "")
        self.page.update()

    def _rebuild_gen_type_row(self) -> None:
        if not self._gen_type_row:
            return
        self._gen_type_row.controls.clear()
        for gtype, icon, label, tooltip in _GENERATION_TYPES:
            is_active = self.state.generation_type == gtype
            btn = ft.Container(
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
                tooltip=tooltip,
                on_click=lambda e, g=gtype: self._set_gen_type(g),
                ink=True,
            )
            self._gen_type_row.controls.append(btn)

    def _new_chat(self, e) -> None:
        if not self.state.current_project:
            self._snack("Select a project first")
            return
        chat = chat_repo.create_chat(project_id=self.state.current_project.id)
        self.state.chats.insert(0, chat)
        self.state.current_chat = chat
        self.reload_messages()
        if self._chat_title_text:
            self._chat_title_text.value = "New Chat"
            self._chat_title_text.update()

    def _inject_prompt(self, text: str) -> None:
        if self._input_field:
            self._input_field.value = text
            self._input_field.update()
            self._input_field.focus()

    def _copy_to_clipboard(self, content: str) -> None:
        self.page.set_clipboard(content)
        self._snack("Copied to clipboard")

    def _save_as_asset(self, msg: Message) -> None:
        if not self.state.current_project:
            self._snack("No project selected — cannot save asset")
            return

        # Detect local image messages
        try:
            parsed = _json.loads(msg.content)
            if parsed.get("__type") == "local_image":
                asset_repo.save_asset(
                    project_id=self.state.current_project.id,
                    asset_type="image",
                    content=parsed["path"],
                    title=parsed.get("prompt", "")[:80],
                    provider="local",
                    model=msg.model,
                )
                self._snack("Image saved to Assets ✓")
                return
        except Exception:
            pass

        type_map = {
            "ad_copy": "text",
            "image_prompt": "image_prompt",
            "video_prompt": "video_prompt",
            "bulk": "bulk",
        }
        asset_type = type_map.get(self.state.generation_type, "text")
        asset_repo.save_asset(
            project_id=self.state.current_project.id,
            asset_type=asset_type,
            content=msg.content,
            provider=msg.provider,
            model=msg.model,
        )
        self._snack("Saved to Assets ✓")

    def _pin_message(self, msg: Message) -> None:
        if msg.id and msg.id != "temp_ai":
            chat_repo.pin_message(msg.id, not msg.pinned)
            self._snack("Message pinned ✓")

    def _schedule_ai_title(self, user_text: str, ai_content: str) -> None:
        """Generate a short AI summary title for the chat in a background thread."""
        if not self.state.current_chat:
            return
        chat = self.state.current_chat
        if chat.title != "New Chat":
            return

        def run():
            try:
                from ai_providers.router import get_provider
                provider = get_provider(self.state.selected_provider)
                messages = [
                    {"role": "user", "content": user_text[:400]},
                    {"role": "assistant", "content": ai_content[:400]},
                    {
                        "role": "user",
                        "content": (
                            "Give this conversation a short title of 4-6 words. "
                            "Output ONLY the title — no quotes, no punctuation, no explanation."
                        ),
                    },
                ]
                result = provider.generate(messages=messages, model=self.state.selected_model)
                if result.ok:
                    title = result.content.strip().strip("\"'").strip()[:60]
                    if title:
                        chat_repo.rename_chat(chat.id, title)
                        chat.title = title
                        if self.state.current_chat and self.state.current_chat.id == chat.id:
                            if self._chat_title_text:
                                self._chat_title_text.value = title
                                try:
                                    self._chat_title_text.update()
                                except Exception:
                                    pass
                        self.state.refresh_chats()
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _open_history(self, e) -> None:
        """Open a searchable chat history modal."""
        if not self.state.current_project:
            self._snack("Select a project first")
            return

        from storage.chat_repo import get_chats_for_project
        all_chats = get_chats_for_project(self.state.current_project.id)

        chat_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=360)
        dlg = ft.AlertDialog(modal=True)

        def close_dlg():
            dlg.open = False
            self.page.update()
            try:
                self.page.overlay.remove(dlg)
            except ValueError:
                pass

        def select_and_close(chat):
            close_dlg()
            self.on_chat_selected(chat)

        def build_items(query: str = "") -> None:
            chat_list_col.controls.clear()
            q = query.lower().strip()
            filtered = [c for c in all_chats if q in c.title.lower()] if q else all_chats
            if not filtered:
                chat_list_col.controls.append(
                    ft.Container(
                        content=ft.Text("No chats match your search", size=12, color=T.TEXT_MUTED),
                        padding=ft.padding.symmetric(horizontal=4, vertical=8),
                    )
                )
            else:
                for chat in filtered:
                    is_active = bool(self.state.current_chat and self.state.current_chat.id == chat.id)
                    date_str = chat.created_at[:10] if chat.created_at else ""
                    chat_list_col.controls.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.CHAT_BUBBLE_OUTLINE,
                                        size=14,
                                        color=T.ACCENT_LIGHT if is_active else T.TEXT_MUTED,
                                    ),
                                    ft.Column(
                                        controls=[
                                            ft.Text(
                                                chat.title,
                                                size=13,
                                                color=T.TEXT_PRIMARY,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Text(date_str, size=10, color=T.TEXT_MUTED),
                                        ],
                                        spacing=2,
                                        tight=True,
                                        expand=True,
                                    ),
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE,
                                        size=14,
                                        color=T.ACCENT_LIGHT,
                                        visible=is_active,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            bgcolor=T.ACCENT_DIM if is_active else T.BG_CARD,
                            border=ft.border.all(1, T.BORDER_ACCENT if is_active else T.BORDER),
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=12, vertical=10),
                            on_click=lambda e, c=chat: select_and_close(c),
                            ink=True,
                        )
                    )
            try:
                chat_list_col.update()
            except Exception:
                pass

        def on_search_change(e):
            build_items(e.control.value)

        search_field = ft.TextField(
            hint_text="Search chats…",
            prefix_icon=ft.Icons.SEARCH,
            on_change=on_search_change,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=T.TEXT_MUTED),
            cursor_color=T.ACCENT_LIGHT,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            autofocus=True,
        )

        build_items()

        dlg.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.MANAGE_SEARCH, color=T.ACCENT_LIGHT, size=18),
                ft.Text(
                    "Chat History",
                    size=15,
                    weight=ft.FontWeight.W_600,
                    color=T.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                ft.Text(f"{len(all_chats)} chats", size=11, color=T.TEXT_MUTED),
            ],
            spacing=8,
        )
        dlg.content = ft.Container(
            content=ft.Column(
                controls=[
                    search_field,
                    ft.Container(height=10),
                    chat_list_col,
                ],
                spacing=0,
                tight=True,
            ),
            width=440,
            padding=ft.padding.only(top=4),
        )
        dlg.bgcolor = T.BG_SECONDARY
        dlg.actions = [
            ft.TextButton(
                "Close",
                on_click=lambda e: close_dlg(),
                style=ft.ButtonStyle(color=T.TEXT_MUTED),
            ),
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.END
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _snack(self, message: str, error: bool = False) -> None:
        self._cur_snackbar = ft.SnackBar(
            content=ft.Text(message, color=T.TEXT_PRIMARY),
            bgcolor=T.ERROR if error else T.BG_CARD,
            action="OK",
        )
        self.page.overlay.append(self._cur_snackbar)
        self._cur_snackbar.open = True
        self.page.update()

    def _current_chat_title(self) -> str:
        if self.state.current_chat:
            return self.state.current_chat.title
        return "No chat selected"

    # ── Public ────────────────────────────────────────────────────────────────

    def on_project_changed(self) -> None:
        """Called when user switches project."""
        if self._chat_title_text:
            self._chat_title_text.value = self._current_chat_title()
        self.reload_messages()

    def on_chat_selected(self, chat: Chat) -> None:
        self.state.current_chat = chat
        if self._chat_title_text:
            self._chat_title_text.value = chat.title
        self.reload_messages()

    def _show_description_suggestion(self, user_text: str) -> None:
        """Insert an inline card asking whether to update the project description."""
        project = self.state.current_project
        if not project:
            return

        current_desc = (project.description or "").strip()
        proposed_initial = current_desc if current_desc else user_text[:400]

        proposal_field = ft.TextField(
            value=proposed_initial,
            multiline=True,
            min_lines=3,
            max_lines=6,
            bgcolor=T.BG_INPUT,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT_PRIMARY,
            hint_text="Edit the description…",
            hint_style=ft.TextStyle(color=T.TEXT_MUTED, size=11),
            cursor_color=T.ACCENT_LIGHT,
            border_radius=8,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),
        )

        card_holder: list[ft.Container] = []

        def _remove_card():
            self._message_list.controls = [
                c for c in self._message_list.controls
                if not card_holder or c is not card_holder[0]
            ]
            try:
                self._message_list.update()
            except Exception:
                pass

        def on_save(e):
            new_desc = (proposal_field.value or "").strip()
            if new_desc and project:
                project.description = new_desc
                _update_project(project)
                self.state.refresh_projects()
                self.app.refresh_brief_if_active()
                self._snack("Project description updated ✓")
            _remove_card()

        def on_skip(e):
            _remove_card()

        hint = (
            "You mentioned something new about your project. Want me to update the description? Edit below:"
            if current_desc else
            "Your project has no description yet. Save what you just said as the project description?"
        )

        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.EDIT_NOTE, size=16, color=T.ACCENT_LIGHT),
                            ft.Text(
                                "Update project description?",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=T.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(hint, size=11, color=T.TEXT_MUTED),
                    proposal_field,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            ft.TextButton(
                                "Skip",
                                on_click=on_skip,
                                style=ft.ButtonStyle(color=T.TEXT_MUTED),
                            ),
                            ft.FilledButton(
                                "Save to description",
                                on_click=on_save,
                                style=ft.ButtonStyle(bgcolor={"": T.ACCENT}),
                            ),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, T.BORDER_ACCENT),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            margin=ft.margin.only(right=48),
        )
        card_holder.append(card)
        self._message_list.controls.append(card)
        try:
            self._message_list.update()
        except Exception:
            pass

    def _show_brief_save_suggestion(self, content: str) -> None:
        """Inline card asking the user to save detected brief data to the brief page."""
        card_holder: list[ft.Container] = []

        def _remove_card():
            self._message_list.controls = [
                c for c in self._message_list.controls
                if not card_holder or c is not card_holder[0]
            ]
            try:
                self._message_list.update()
            except Exception:
                pass

        def on_save(e):
            project = self.state.current_project
            if project and _parse_brief_from_ai(content, project):
                fresh = _get_project(project.id)
                if fresh:
                    self.state.current_project = fresh
                self.app.refresh_brief_if_active()
                self._snack("Brief saved ✓  —  Check the Brief page")
            else:
                self._snack("Could not save brief fields", error=True)
            _remove_card()

        def on_skip(e):
            _remove_card()

        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CAMPAIGN_OUTLINED, size=16, color=T.ACCENT_LIGHT),
                            ft.Text(
                                "Save to Brief page?",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=T.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "I found marketing brief information in my response. Save it to your Brief page?",
                        size=11,
                        color=T.TEXT_MUTED,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            ft.TextButton(
                                "Not now",
                                on_click=on_skip,
                                style=ft.ButtonStyle(color=T.TEXT_MUTED),
                            ),
                            ft.FilledButton(
                                "Save to Brief",
                                icon=ft.Icons.SAVE_OUTLINED,
                                on_click=on_save,
                                style=ft.ButtonStyle(bgcolor={"": T.ACCENT}),
                            ),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=T.BG_CARD,
            border=ft.border.all(1, T.BORDER_ACCENT),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            margin=ft.margin.only(right=48),
        )
        card_holder.append(card)
        self._message_list.controls.append(card)
        try:
            self._message_list.update()
        except Exception:
            pass

    def _save_content_to_brief(self, content: str) -> None:
        project = self.state.current_project
        if not project:
            self._snack("No project selected", error=True)
            return
        if _parse_brief_from_ai(content, project):
            fresh = _get_project(project.id)
            if fresh:
                self.state.current_project = fresh
            self.app.refresh_brief_if_active()
            self._snack("Brief saved ✓  —  Check the Brief page")
        else:
            self._snack("Not enough brief fields found in this message", error=True)

    def trigger_brief_interview(self) -> None:
        """Called from BriefView — auto-starts the AI marketing interview."""
        if self.state.is_generating:
            return
        self._dispatch(_BRIEF_FILL_API_TEXT, display_text="Help me fill my marketing brief")


def _is_empty_state(container: ft.Container) -> bool:
    """Detect the empty state container to remove it before first message."""
    try:
        return (
            isinstance(container.content, ft.Column)
            and any(
                isinstance(c, ft.Text) and "Start a conversation" in (c.value or "")
                for c in container.content.controls
            )
        )
    except Exception:
        return False
