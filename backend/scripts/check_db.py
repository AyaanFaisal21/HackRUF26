"""Check that the database in DATABASE_URL has what Day Zero needs. usage: .venv/bin/python backend/scripts/check_db.py"""
import os, sys
from dotenv import load_dotenv
import psycopg
load_dotenv()
url = os.environ.get("DATABASE_URL") or sys.exit("DATABASE_URL not set in .env")
with psycopg.connect(url) as conn:
    print("connected to", conn.execute("SELECT version()").fetchone()[0][:60])
    avail = {r[0]: r[1] for r in conn.execute("SELECT name, default_version FROM pg_available_extensions WHERE name IN ('timescaledb','vector','vectorscale','ai')")}
    for ext in ("timescaledb", "vector", "vectorscale", "ai"):
        print(f"  {ext:12} {'available ' + avail[ext] if ext in avail else 'NOT available'}{'  (required)' if ext in ('timescaledb', 'vector') else '  (optional)'}")
    if "vector" in avail and "timescaledb" in avail:
        print("OK: run `make db-init` then `make load` and `make load-trial`")
    else:
        print("This service is missing a required extension. Create the service with the AI and vector option.")
