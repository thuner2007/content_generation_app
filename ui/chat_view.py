"""Main chat workspace view."""
import threading
import flet as ft
from typing import TYPE_CHECKING

from ui import theme as T
from storage.models import Message, Chat
from storage import chat_repo, asset_repo
from core import dispatcher
from core.app_state import AppState
from ai_providers.router import list_providers, get_models_for_provider

if TYPE_CHECKING:
    from ui.layout import AppLayout

_GENERATION_TYPES = [
    ("chat",          ft.Icons.CHAT_BUBBLE_OUTLINE,     "Chat",          "Free-form AI conversation"),
    ("ad_copy",       ft.Icons.TEXT_FIELDS,              "Ad Copy",       "Generate ad headlines & copy"),
    ("image_prompt",  ft.Icons.IMAGE_OUTLINED,           "Image Prompt",  "Prompts for AI image generators"),
    ("video_prompt",  ft.Icons.MOVIE_OUTLINED,           "Video Prompt",  "Prompts for AI video generators"),
    ("bulk",          ft.Icons.FORMAT_LIST_BULLETED,     "10 Variations", "Generate 10 ad variations"),
    ("product_ideas", ft.Icons.LIGHTBULB_OUTLINE,        "Product Ideas", "Marketing angles & ideas"),
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
        self._chat_title_text: ft.Text | None = None
        self._model_dropdown: ft.Dropdown | None = None
        self._provider_dropdown: ft.Dropdown | None = None
        self._gen_type_row: ft.Row | None = None
        self._root: ft.Column | None = None

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self) -> ft.Column:
        self._chat_title_text = ft.Text(
            self._current_chat_title(),
            size=14,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
        )
        self._typing_indicator = ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=T.ACCENT),
                    ft.Text("Generating…", size=12, color=T.TEXT_MUTED),
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
        self._provider_dropdown = ft.Dropdown(
            value=self.state.selected_provider,
            options=[ft.dropdown.Option(p, p.capitalize()) for p in list_providers()],
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
        return ft.Container(
            content=ft.Row(
                controls=[self._input_field, self._send_btn],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.END,
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

        # Message text
        text_control = ft.Markdown(
            msg.content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme="atom-one-dark",
            code_style=ft.TextStyle(
                font_family="monospace",
                size=12,
                color=T.TEXT_PRIMARY,
            ),
            on_tap_link=lambda e: self.page.launch_url(e.data),
        ) if not is_user else ft.Text(
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

        row_controls = (
            [ft.Container(expand=True), bubble, avatar]
            if is_user
            else [avatar, bubble, ft.Container(expand=True)]
        )

        return ft.Row(
            controls=row_controls,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_send(self, e) -> None:
        text = self._input_field.value.strip() if self._input_field else ""
        if not text or self.state.is_generating:
            return
        self._dispatch(text)

    def _dispatch(self, text: str) -> None:
        """Send message to AI in a background thread."""
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

        # Optimistic user bubble
        user_msg = Message(
            id="temp",
            chat_id="",
            role="user",
            content=text,
        )
        self._message_list.controls.append(self._make_bubble(user_msg))
        self.page.update()

        def run():
            try:
                result = dispatcher.generate(state=self.state, user_input=text)

                if result.ok:
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
                    # Update chat title from first message if still "New Chat"
                    self._maybe_auto_title(text)
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

    def _on_provider_change(self, e) -> None:
        self.state.selected_provider = e.control.value
        models = get_models_for_provider(self.state.selected_provider)
        self.state.selected_model = models[0] if models else ""
        if self._model_dropdown:
            self._model_dropdown.options = [ft.dropdown.Option(m) for m in models]
            self._model_dropdown.value = self.state.selected_model
            self._model_dropdown.update()
        self.app.refresh_right_panel()

    def _on_model_change(self, e) -> None:
        self.state.selected_model = e.control.value
        self.app.refresh_right_panel()

    def _set_gen_type(self, gtype: str) -> None:
        self.state.generation_type = gtype
        self._rebuild_gen_type_row()
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

    def _maybe_auto_title(self, first_message: str) -> None:
        if not self.state.current_chat:
            return
        chat = self.state.current_chat
        if chat.title == "New Chat":
            new_title = first_message[:40] + ("…" if len(first_message) > 40 else "")
            chat_repo.rename_chat(chat.id, new_title)
            chat.title = new_title
            if self._chat_title_text:
                self._chat_title_text.value = new_title

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
