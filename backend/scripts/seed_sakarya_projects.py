"""Manually seeds a handful of major Sakarya infrastructure projects, per the
MVP plan (manual data entry before any scraping bot exists).

NOTE: coordinates below are approximate placeholders and must be verified
against real sources (KGM, TCDD, ÇED reports) before being treated as fact.

Run with, from the backend/ directory:

    python scripts/seed_sakarya_projects.py
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
        name="Sakarya YHT Garı",
        project_type=ProjectType.RAILWAY,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.7730,
        longitude=30.4030,
        importance=1.0,
        description="Istanbul-Ankara YHT hatti Sakarya istasyonu (placeholder konum, dogrulanmali).",
    ),
    Project(
        id=None,
        name="Sakarya OSB",
        project_type=ProjectType.INDUSTRIAL_ZONE,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.6890,
        longitude=30.4180,
        importance=0.8,
        description="Sakarya Organize Sanayi Bolgesi (placeholder konum, dogrulanmali).",
    ),
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
    Project(
        id=None,
        name="D-100 / TEM Baglanti Yolu",
        project_type=ProjectType.HIGHWAY,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.7550,
        longitude=30.3500,
        importance=0.7,
        description="Otoban baglanti noktasi (placeholder konum, dogrulanmali).",
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
    print(f"Seeded {len(SAMPLE_PROJECTS)} sample projects for Sakarya.")
