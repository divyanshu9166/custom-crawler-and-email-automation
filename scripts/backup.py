"""Consistent SQLite backup, including WAL data. Does not delete existing backups."""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from outreach.config import Settings

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="backups")
args = parser.parse_args()
settings = Settings()
if not settings.database.exists():
    raise SystemExit("No database found")
folder = Path(args.output)
folder.mkdir(parents=True, exist_ok=True)
target = folder / ("outreach-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db")
with sqlite3.connect(settings.database) as source, sqlite3.connect(target) as dest:
    source.backup(dest)
    if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Backup integrity check failed")
target.chmod(0o600)
print(f"Verified backup: {target.resolve()}")
