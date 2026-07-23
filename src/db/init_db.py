"""
src/db/init_db.py — creates all tables from models.py against DATABASE_URL.

Run once after creating the local database (see docs/postgres-setup.md):
  python src/db/init_db.py

Safe to re-run: create_all() only creates tables that don't already exist,
it never drops or alters existing ones. If you change a column later you'll
need a real migration tool (Alembic) rather than relying on this script —
fine for now, worth adding once the schema stabilises.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `from db.models import ...`

from dotenv import load_dotenv
from sqlalchemy import create_engine

from db.models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if __name__ == "__main__":
    if not DATABASE_URL:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill in DATABASE_URL — "
              "see docs/postgres-setup.md for the local Postgres connection string format.")
        sys.exit(1)

    engine = create_engine(DATABASE_URL, echo=True)
    Base.metadata.create_all(engine)
    print("Done. Tables created (or already existed): "
          + ", ".join(Base.metadata.tables.keys()))
