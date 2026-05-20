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
    return Project(
        id=row["id"],
        name=row["name"],
        slogan=row["slogan"] or "",
        brand_colors=row["brand_colors"] or "",
        fonts=row["fonts"] or "",
        logo_path=row["logo_path"] or "",
        legal_info=row["legal_info"] or "",
        description=row["description"] or "",
        marketing_brief=row["marketing_brief"] or "",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )
