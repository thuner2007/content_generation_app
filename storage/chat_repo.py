"""Chat and Message CRUD operations."""
import uuid
from typing import Optional

from storage.db import get_connection
from storage.models import Chat, Message


# ── Chats ──────────────────────────────────────────────────────────────────────

def create_chat(project_id: Optional[str] = None, title: str = "New Chat") -> Chat:
    chat_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO chats (id, project_id, title) VALUES (?, ?, ?)",
            (chat_id, project_id, title),
        )
        conn.commit()
    finally:
        conn.close()
    return Chat(id=chat_id, project_id=project_id, title=title)


def get_chats_for_project(project_id: str) -> list[Chat]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chats WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_chat(r) for r in rows]
    finally:
        conn.close()


def get_chat(chat_id: str) -> Optional[Chat]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return _row_to_chat(row) if row else None
    finally:
        conn.close()


def rename_chat(chat_id: str, title: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
        conn.commit()
    finally:
        conn.close()


def delete_chat(chat_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()


# ── Messages ───────────────────────────────────────────────────────────────────

def add_message(
    chat_id: str,
    role: str,
    content: str,
    provider: str = "",
    model: str = "",
    tokens_used: int = 0,
    cost: float = 0.0,
) -> Message:
    msg_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO messages
               (id, chat_id, role, content, provider, model, tokens_used, cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, chat_id, role, content, provider, model, tokens_used, cost),
        )
        conn.commit()
    finally:
        conn.close()
    return Message(
        id=msg_id,
        chat_id=chat_id,
        role=role,
        content=content,
        provider=provider,
        model=model,
        tokens_used=tokens_used,
        cost=cost,
    )


def get_messages(chat_id: str) -> list[Message]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
        return [_row_to_message(r) for r in rows]
    finally:
        conn.close()


def search_messages_global(query: str) -> list[Message]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT 50",
            (f"%{query}%",),
        ).fetchall()
        return [_row_to_message(r) for r in rows]
    finally:
        conn.close()


def pin_message(msg_id: str, pinned: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE messages SET pinned = ? WHERE id = ?",
            (1 if pinned else 0, msg_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_chat(row) -> Chat:
    return Chat(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"] or "New Chat",
        created_at=row["created_at"] or "",
    )


def _row_to_message(row) -> Message:
    return Message(
        id=row["id"],
        chat_id=row["chat_id"],
        role=row["role"],
        content=row["content"],
        provider=row["provider"] or "",
        model=row["model"] or "",
        tokens_used=row["tokens_used"] or 0,
        cost=row["cost"] or 0.0,
        pinned=bool(row["pinned"]),
        created_at=row["created_at"] or "",
    )
