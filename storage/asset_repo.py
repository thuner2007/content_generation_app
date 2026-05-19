"""Asset, API key, and usage log CRUD."""
import uuid
from typing import Optional

from storage.db import get_connection
from storage.models import Asset, UsageLog


# ── Assets ─────────────────────────────────────────────────────────────────────

def save_asset(
    project_id: str,
    asset_type: str,
    content: str,
    title: str = "",
    tags: str = "",
    provider: str = "",
    model: str = "",
) -> Asset:
    asset_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO assets (id, project_id, type, title, content, tags, provider, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, project_id, asset_type, title, content, tags, provider, model),
        )
        conn.commit()
    finally:
        conn.close()
    return Asset(
        id=asset_id,
        project_id=project_id,
        type=asset_type,
        title=title,
        content=content,
        tags=tags,
        provider=provider,
        model=model,
    )


def get_assets(project_id: str, asset_type: Optional[str] = None) -> list[Asset]:
    conn = get_connection()
    try:
        if asset_type:
            rows = conn.execute(
                "SELECT * FROM assets WHERE project_id=? AND type=? ORDER BY created_at DESC",
                (project_id, asset_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assets WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    finally:
        conn.close()


def delete_asset(asset_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.commit()
    finally:
        conn.close()


# ── API Keys ───────────────────────────────────────────────────────────────────

def save_api_key(provider: str, api_key: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO api_keys (provider, api_key) VALUES (?, ?)
               ON CONFLICT(provider) DO UPDATE SET api_key=excluded.api_key,
               updated_at=CURRENT_TIMESTAMP""",
            (provider, api_key),
        )
        conn.commit()
    finally:
        conn.close()


def get_api_key(provider: str) -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT api_key FROM api_keys WHERE provider = ?", (provider,)
        ).fetchone()
        return row["api_key"] if row else None
    finally:
        conn.close()


def get_all_api_keys() -> dict[str, str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT provider, api_key FROM api_keys").fetchall()
        return {r["provider"]: r["api_key"] for r in rows}
    finally:
        conn.close()


# ── Usage Logs ─────────────────────────────────────────────────────────────────

def log_usage(
    provider: str,
    model: str,
    tokens_input: int,
    tokens_output: int,
    cost: float,
    project_id: str = "",
    generation_type: str = "chat",
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO usage_logs
               (id, project_id, provider, model, tokens_input, tokens_output, cost, generation_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                project_id,
                provider,
                model,
                tokens_input,
                tokens_output,
                cost,
                generation_type,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_total_cost(project_id: Optional[str] = None) -> float:
    conn = get_connection()
    try:
        if project_id:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost), 0) as total FROM usage_logs WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost), 0) as total FROM usage_logs"
            ).fetchone()
        return float(row["total"])
    finally:
        conn.close()


def get_usage_summary() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT provider,
                      SUM(tokens_input + tokens_output) as total_tokens,
                      SUM(cost) as total_cost,
                      COUNT(*) as requests
               FROM usage_logs
               GROUP BY provider
               ORDER BY total_cost DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_usage(limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM usage_logs ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_asset(row) -> Asset:
    return Asset(
        id=row["id"],
        project_id=row["project_id"],
        type=row["type"],
        title=row["title"] or "",
        content=row["content"],
        tags=row["tags"] or "",
        provider=row["provider"] or "",
        model=row["model"] or "",
        created_at=row["created_at"] or "",
    )
