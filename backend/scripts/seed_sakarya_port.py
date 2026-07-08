"""Manually seeds the one Sakarya project category that still lacks an
automated data source: the port (Karasu Limani). Highways, railways,
industrial zones, and bus stops are now handled by
scripts/ingest_sakarya_osm.py using real OpenStreetMap data - this script
used to also seed placeholder versions of those, but they've been removed
here to avoid reintroducing stale/fake rows alongside the real ones.

NOTE: the coordinates below are an approximate placeholder and must be
verified against a real source before being treated as fact.

Run with, from the backend/ directory:

    python scripts/seed_sakarya_port.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.project import Project, ProjectStatus, ProjectType  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.repositories.project_repository import (  # noqa: E402
    SqlAlchemyProjectRepository,
)

SAMPLE_PROJECTS = [
    Project(
        id=None,
        name="Karasu Limani",
        project_type=ProjectType.PORT,
        status=ProjectStatus.UNDER_CONSTRUCTION,
        city="sakarya",
        latitude=41.1180,
        longitude=30.6980,
        importance=0.9,
        description="Karasu Limani projesi (placeholder konum, dogrulanmali).",
    ),
]


def seed() -> None:
    session = SessionLocal()
    try:
        repo = SqlAlchemyProjectRepository(session)
        for project in SAMPLE_PROJECTS:
            repo.add(project)
    finally:
        session.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(SAMPLE_PROJECTS)} sample project(s) for Sakarya.")
