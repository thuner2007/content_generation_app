"""CRUD operations for project products."""
from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from typing import Optional

from storage.db import get_connection, _lock
from storage.models import Product


def _row_to_product(row) -> Product:
    keys = row.keys()
    return Product(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        description=row["description"] if "description" in keys else "",
        price=row["price"] if "price" in keys else "",
        url=row["url"] if "url" in keys else "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_products(project_id: str) -> list[Product]:
    with _lock:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM products WHERE project_id=? ORDER BY created_at ASC",
                (project_id,),
            ).fetchall()
            return [_row_to_product(r) for r in rows]
        finally:
            conn.close()


def get_product(product_id: str) -> Optional[Product]:
    with _lock:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM products WHERE id=?", (product_id,)
            ).fetchone()
            return _row_to_product(row) if row else None
        finally:
            conn.close()


def create_product(
    project_id: str,
    name: str,
    description: str = "",
    price: str = "",
    url: str = "",
) -> Product:
    now = datetime.utcnow().isoformat()
    pid = str(uuid4())
    with _lock:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO products
                   (id, project_id, name, description, price, url, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (pid, project_id, name, description, price, url, now, now),
            )
            conn.commit()
        finally:
            conn.close()
    return Product(
        id=pid, project_id=project_id, name=name,
        description=description, price=price, url=url,
        created_at=now, updated_at=now,
    )


def update_product(product: Product) -> None:
    now = datetime.utcnow().isoformat()
    with _lock:
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE products SET
                   name=?, description=?, price=?, url=?, updated_at=?
                   WHERE id=?""",
                (product.name, product.description, product.price,
                 product.url, now, product.id),
            )
            conn.commit()
        finally:
            conn.close()


def delete_product(product_id: str) -> None:
    with _lock:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM products WHERE id=?", (product_id,))
            conn.commit()
        finally:
            conn.close()
