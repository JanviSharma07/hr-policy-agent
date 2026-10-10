"""Adds new columns to tables that already exist.

create_all() only creates missing tables; it never changes existing ones.
This adds any missing columns on startup, so no data is lost."""
from sqlalchemy import inspect, text

NEW_COLUMNS = {
    "users": {
        "join_date": "DATE",
        "grade": "VARCHAR(20)",
        "city": "VARCHAR(100)",
    },
    "documents": {
        "family_id": "INTEGER",
        "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
    },
}


def run_migrations(engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in NEW_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
        # Every document is its own family until it gets replaced
        conn.execute(text("UPDATE documents SET family_id = id WHERE family_id IS NULL"))
