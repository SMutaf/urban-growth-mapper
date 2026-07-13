"""Creates the PostGIS extension and all tables. Run once against a fresh database,
from the backend/ directory:

    python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.infrastructure.persistence import models  # noqa: F401,E402 (registers models on Base)
from app.infrastructure.persistence.database import Base, engine  # noqa: E402


def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Base.metadata.create_all only creates missing tables, it never
        # alters existing ones (this project has no Alembic migrations) -
        # so a column added to an already-existing table (like
        # DistrictBoundaryModel.mahalle_name) needs an explicit, idempotent
        # ALTER here to reach a database that already had the table.
        conn.execute(text("ALTER TABLE district_boundaries ADD COLUMN IF NOT EXISTS mahalle_name VARCHAR"))
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized (PostGIS extension + tables created).")
