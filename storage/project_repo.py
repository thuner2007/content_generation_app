"""Project CRUD operations."""
import uuid
from typing import Optional

from storage.db import get_connection
from storage.models import Project


def create_project(name: str, **kwargs) -> Project:
    project_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO projects (id, name, slogan, brand_colors, fonts, logo_path, legal_info, description, marketing_brief)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                name,
                kwargs.get("slogan", ""),
                kwargs.get("brand_colors", ""),
                kwargs.get("fonts", ""),
                kwargs.get("logo_path", ""),
                kwargs.get("legal_info", ""),
                kwargs.get("description", ""),
                kwargs.get("marketing_brief", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_project(project_id)


def get_project(project_id: str) -> Optional[Project]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None
    finally:
        conn.close()


def get_all_projects() -> list[Project]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [_row_to_project(r) for r in rows]
    finally:
        conn.close()


def update_project(project: Project) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE projects SET name=?, slogan=?, brand_colors=?, fonts=?,
               logo_path=?, legal_info=?, description=?, marketing_brief=?,
               image_style=?, tone_of_voice=?, brand_values=?,
               voiceover_voice=?, music_mood=?, video_style=?,
               target_audience=?, content_pillars=?, hashtags=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (
                project.name,
                project.slogan,
                project.brand_colors,
                project.fonts,
                project.logo_path,
                project.legal_info,
                project.description,
                project.marketing_brief,
                project.image_style,
                project.tone_of_voice,
                project.brand_values,
                project.voiceover_voice,
                project.music_mood,
                project.video_style,
                project.target_audience,
                project.content_pillars,
                project.hashtags,
                project.id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_project(project_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()


def _row_to_project(row) -> Project:
    keys = row.keys()
    def _get(col): return row[col] if col in keys else ""
    return Project(
        id=row["id"],
        name=row["name"],
        slogan=_get("slogan"),
        brand_colors=_get("brand_colors"),
        fonts=_get("fonts"),
        logo_path=_get("logo_path"),
        legal_info=_get("legal_info"),
        description=_get("description"),
        marketing_brief=_get("marketing_brief"),
        image_style=_get("image_style"),
        tone_of_voice=_get("tone_of_voice"),
        brand_values=_get("brand_values"),
        voiceover_voice=_get("voiceover_voice"),
        music_mood=_get("music_mood"),
        video_style=_get("video_style"),
        target_audience=_get("target_audience"),
        content_pillars=_get("content_pillars"),
        hashtags=_get("hashtags"),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )
