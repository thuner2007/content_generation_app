"""CRUD operations for ad campaigns."""
from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from typing import Optional

from storage.db import get_connection, _lock
from storage.models import Campaign


def _row_to_campaign(row) -> Campaign:
    keys = row.keys()
    return Campaign(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        status=row["status"],
        strategy=row["strategy"],
        objective=row["objective"],
        platforms=row["platforms"],
        daily_budget=row["daily_budget"],
        total_budget=row["total_budget"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        target_audience=row["target_audience"],
        notes=row["notes"],
        product_name=row["product_name"] if "product_name" in keys else "",
        product_description=row["product_description"] if "product_description" in keys else "",
        video_ideas=row["video_ideas"] if "video_ideas" in keys else "[]",
        product_ids=row["product_ids"] if "product_ids" in keys else "[]",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_campaigns(project_id: str) -> list[Campaign]:
    with _lock:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM campaigns WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            return [_row_to_campaign(r) for r in rows]
        finally:
            conn.close()


def get_campaign(campaign_id: str) -> Optional[Campaign]:
    with _lock:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            return _row_to_campaign(row) if row else None
        finally:
            conn.close()


def create_campaign(
    project_id: str,
    name: str,
    strategy: str = "",
    objective: str = "",
    platforms: str = "[]",
    daily_budget: float = 0.0,
    total_budget: float = 0.0,
    start_date: str = "",
    end_date: str = "",
    target_audience: str = "",
    notes: str = "",
    product_name: str = "",
    product_description: str = "",
    video_ideas: str = "[]",
) -> Campaign:
    now = datetime.utcnow().isoformat()
    cid = str(uuid4())
    with _lock:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO campaigns
                   (id, project_id, name, status, strategy, objective, platforms,
                    daily_budget, total_budget, start_date, end_date,
                    target_audience, notes, product_name, product_description,
                    video_ideas, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, project_id, name, "draft", strategy, objective, platforms,
                    daily_budget, total_budget, start_date, end_date,
                    target_audience, notes, product_name, product_description,
                    video_ideas, now, now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return Campaign(
        id=cid, project_id=project_id, name=name, status="draft",
        strategy=strategy, objective=objective, platforms=platforms,
        daily_budget=daily_budget, total_budget=total_budget,
        start_date=start_date, end_date=end_date,
        target_audience=target_audience, notes=notes,
        product_name=product_name, product_description=product_description,
        video_ideas=video_ideas, created_at=now, updated_at=now,
    )


def update_campaign(campaign: Campaign) -> None:
    now = datetime.utcnow().isoformat()
    with _lock:
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE campaigns SET
                   name=?, status=?, strategy=?, objective=?, platforms=?,
                   daily_budget=?, total_budget=?, start_date=?, end_date=?,
                   target_audience=?, notes=?, product_name=?,
                   product_description=?, video_ideas=?, product_ids=?, updated_at=?
                   WHERE id=?""",
                (
                    campaign.name, campaign.status, campaign.strategy,
                    campaign.objective, campaign.platforms,
                    campaign.daily_budget, campaign.total_budget,
                    campaign.start_date, campaign.end_date,
                    campaign.target_audience, campaign.notes,
                    campaign.product_name, campaign.product_description,
                    campaign.video_ideas, campaign.product_ids, now, campaign.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def delete_campaign(campaign_id: str) -> None:
    with _lock:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM campaigns WHERE id=?", (campaign_id,))
            conn.commit()
        finally:
            conn.close()


def set_status(campaign_id: str, status: str) -> None:
    now = datetime.utcnow().isoformat()
    with _lock:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE campaigns SET status=?, updated_at=? WHERE id=?",
                (status, now, campaign_id),
            )
            conn.commit()
        finally:
            conn.close()
