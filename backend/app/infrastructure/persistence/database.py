import os

# On a non-English Windows locale (e.g. Turkish, cp1254), libpq localizes its own
# error messages and encodes them in the system codepage, not UTF-8. psycopg2 then
# crashes with an opaque UnicodeDecodeError instead of surfacing the real Postgres
# error. Forcing English messages keeps every future DB error readable.
os.environ.setdefault("LANGUAGE", "en_US:en")
os.environ.setdefault("PGCLIENTENCODING", "UTF8")

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
