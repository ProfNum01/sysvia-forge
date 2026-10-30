"""Data-preserving SQLite upgrades. Existing orders, images and results are retained."""
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable


def upgrade_local_schema(engine):
    columns = {
        "inspections": {
            "image_width": "INTEGER NOT NULL DEFAULT 0", "image_height": "INTEGER NOT NULL DEFAULT 0",
            "creation_key": "VARCHAR",
            "processing_stage": "VARCHAR NOT NULL DEFAULT 'HISTORICAL_RECORD'",
            "reconciliation_status": "VARCHAR NOT NULL DEFAULT 'NEEDS_REVIEW'",
            "comparison": "JSON NOT NULL DEFAULT '[]'", "regions": "JSON NOT NULL DEFAULT '[]'",
            "provider_error_details": "JSON",
            "investigation_id": "VARCHAR", "investigation_status": "VARCHAR NOT NULL DEFAULT 'NOT_STARTED'",
            "investigation_result": "JSON", "investigation_error": "JSON", "investigation_key": "VARCHAR",
            "investigation_started_at": "VARCHAR", "investigation_completed_at": "VARCHAR",
        },
        "inspection_observations": {
            "sku": "VARCHAR", "identification_status": "VARCHAR NOT NULL DEFAULT 'UNCERTAIN'",
            "evidence_region_ids": "JSON NOT NULL DEFAULT '[]'",
        },
        "orders": {"shipping_status": "VARCHAR NOT NULL DEFAULT 'NOT_READY'",
                   "requires_reinspection": "BOOLEAN NOT NULL DEFAULT 0"},
        "corrective_actions": {
            "investigation_id": "VARCHAR", "evidence_references": "JSON NOT NULL DEFAULT '[]'",
            "lifecycle_state": "VARCHAR NOT NULL DEFAULT 'PROPOSED'", "rejection_key": "VARCHAR",
            "rejection_reason": "TEXT", "error_details": "JSON",
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
        for column in ("investigation_key", "investigation_id"):
            connection.exec_driver_sql(f'CREATE UNIQUE INDEX IF NOT EXISTS ix_inspections_{column} ON inspections ({column})')
        connection.exec_driver_sql("UPDATE corrective_actions SET lifecycle_state = CASE WHEN status = 'EXECUTED' THEN 'AWAITING_REINSPECTION' ELSE status END WHERE lifecycle_state = 'PROPOSED' AND status <> 'PROPOSED'")
        connection.exec_driver_sql("UPDATE orders SET shipping_status='HELD', requires_reinspection=1 WHERE status='HELD'")
    if engine.dialect.name == "sqlite":
        _upgrade_action_constraint(engine)


def _upgrade_action_constraint(engine):
    """Replace SQLite's legacy two-action CHECK, preserving every action and FK."""
    from backend.app.models.database import CorrectiveAction
    with engine.connect() as connection:
        definition = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='corrective_actions'").scalar_one()
        connection.commit()
        if "HOLD_SHIPMENT" not in definition:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            try:
                with connection.begin():
                    ddl = str(CreateTable(CorrectiveAction.__table__).compile(dialect=engine.dialect))
                    ddl = ddl.replace("CREATE TABLE corrective_actions", "CREATE TABLE corrective_actions_upgrade", 1)
                    connection.exec_driver_sql(ddl)
                    names = ', '.join(f'"{column.name}"' for column in CorrectiveAction.__table__.columns)
                    connection.exec_driver_sql(f"INSERT INTO corrective_actions_upgrade ({names}) SELECT {names} FROM corrective_actions")
                    connection.exec_driver_sql("DROP TABLE corrective_actions")
                    connection.exec_driver_sql("ALTER TABLE corrective_actions_upgrade RENAME TO corrective_actions")
                    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                        raise RuntimeError("Action schema upgrade failed foreign-key validation")
            finally:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_corrective_actions_rejection_key ON corrective_actions (rejection_key)")
        connection.commit()
