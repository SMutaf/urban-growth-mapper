FROM python:3.11-slim

# geopandas/rasterio (used only by the offline resolution-sensitivity
# analysis, backend/analysis/) need GDAL's native libraries at import time
# even though the served API never touches them - installed here so
# `pip install -r requirements.txt` doesn't fail on a bare python:slim image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# init_db.py is idempotent (CREATE EXTENSION IF NOT EXISTS / create_all /
# ADD COLUMN IF NOT EXISTS - see the file itself) so running it on every
# container start is safe; it's what actually creates the schema on a
# fresh database volume. Real Sakarya data still needs the scripts/
# ingest_*.py scripts run manually once (see README) - they hit live
# external APIs and shouldn't run unattended on every restart.
CMD ["sh", "-c", "python scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
