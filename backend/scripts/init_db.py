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


if __name__ == "__main__":
    init_db()
    print("Database initialized (PostGIS extension + tables created).")
