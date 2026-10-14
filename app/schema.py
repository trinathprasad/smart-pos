from __future__ import annotations

from sqlalchemy import inspect, text

from .extensions import db


def normalize_category_name(value: str | None) -> str:
    return (value or "").strip().casefold()


def upgrade_category_schema() -> None:
    """Create and backfill managed categories without removing legacy data.

    Archived products retain their legacy category text for historical display,
    but must not recreate a managed category that was intentionally deleted.
    """
    db.create_all()
    inspector = inspect(db.engine)
    category_columns = {column["name"] for column in inspector.get_columns("category")}
    if "image_path" not in category_columns:
        db.session.execute(text("ALTER TABLE category ADD COLUMN image_path VARCHAR(255)"))

    product_columns = {column["name"] for column in inspector.get_columns("product")}

    if "category_id" not in product_columns:
        db.session.execute(text("ALTER TABLE product ADD COLUMN category_id INTEGER REFERENCES category(id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_product_category_id ON product (category_id)"))

    category_rows = db.session.execute(
        text("SELECT id, normalized_name FROM category ORDER BY id")
    ).mappings().all()
    categories_by_normalized = {row["normalized_name"]: row["id"] for row in category_rows}

    products = db.session.execute(
        text(
            "SELECT id, category, category_id FROM product "
            "WHERE category IS NOT NULL AND is_active = 1 ORDER BY id"
        )
    ).mappings().all()
    for product in products:
        normalized_name = normalize_category_name(product["category"])
        display_name = (product["category"] or "").strip()
        if not normalized_name or product["category_id"] is not None:
            continue

        category_id = categories_by_normalized.get(normalized_name)
        if category_id is None:
            result = db.session.execute(
                text(
                    "INSERT INTO category (name, normalized_name, created_at, updated_at) "
                    "VALUES (:name, :normalized_name, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"name": display_name, "normalized_name": normalized_name},
            )
            category_id = result.lastrowid
            categories_by_normalized[normalized_name] = category_id

        db.session.execute(
            text("UPDATE product SET category_id = :category_id WHERE id = :product_id"),
            {"category_id": category_id, "product_id": product["id"]},
        )

    db.session.commit()
