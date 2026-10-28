"""Additive SQLite upgrades only. Existing orders, images and results are retained."""
from sqlalchemy import inspect


def upgrade_local_schema(engine):
    columns = {
        "inspections": {
            "image_width": "INTEGER NOT NULL DEFAULT 0", "image_height": "INTEGER NOT NULL DEFAULT 0",
            "creation_key": "VARCHAR",
            "processing_stage": "VARCHAR NOT NULL DEFAULT 'HISTORICAL_RECORD'",
            "reconciliation_status": "VARCHAR NOT NULL DEFAULT 'NEEDS_REVIEW'",
            "comparison": "JSON NOT NULL DEFAULT '[]'", "regions": "JSON NOT NULL DEFAULT '[]'",
            "provider_error_details": "JSON",
        },
        "inspection_observations": {
            "sku": "VARCHAR", "identification_status": "VARCHAR NOT NULL DEFAULT 'UNCERTAIN'",
            "evidence_region_ids": "JSON NOT NULL DEFAULT '[]'",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, additions in columns.items():
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, declaration in additions.items():
                if name not in existing:
                    connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}')
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_inspections_creation_key ON inspections (creation_key)")
