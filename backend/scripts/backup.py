"""Dump every table to one timestamped JSON file.

No pg_dump needed — it uses the SQLAlchemy connection the app already has, so
there is nothing extra to install and no password to type. Point --out at a
synced folder (OneDrive, Google Drive, Dropbox) and the copy leaves the machine
on its own.

    python scripts/backup.py
    python scripts/backup.py --out "C:/Users/qusai/OneDrive/SEZER-backups"
    python scripts/backup.py --keep 20

Tables are written in foreign-key order, so a restore can replay them top to
bottom without tripping a constraint.
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text                # noqa: E402
from app.database import Base, SessionLocal        # noqa: E402
import app.models                                  # noqa: E402,F401  (registers the tables)

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "backups"


def _encode(value):
    """Make a column value JSON-safe without losing precision."""
    if isinstance(value, Decimal):
        return str(value)          # str, not float — money must not round
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def dump(out_dir: Path, keep: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"sezer-{stamp}.json"

    db = SessionLocal()
    try:
        # Alembic's table is not part of the app's metadata, but a restore is
        # meaningless without knowing which schema these rows came from.
        schema_version = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()

        payload = {
            "taken_at": datetime.now(tz=timezone.utc).isoformat(),
            "schema_version": schema_version,
            "note": "SEZER database dump. Tables are in foreign-key order.",
            "tables": {},
        }
        # sorted_tables resolves dependencies: parents before children
        for table in Base.metadata.sorted_tables:
            rows = db.execute(select(table)).mappings().all()
            payload["tables"][table.name] = [
                {k: _encode(v) for k, v in row.items()} for row in rows
            ]
            print(f"  {table.name:28} {len(rows):>7} rows")
    finally:
        db.close()

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # keep the newest N, drop the rest
    existing = sorted(out_dir.glob("sezer-*.json"))
    for stale in existing[:-keep] if keep > 0 else []:
        stale.unlink()
        print(f"  removed old backup {stale.name}")

    return target


def main():
    ap = argparse.ArgumentParser(description="Back up the SEZER database to JSON.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"where to write (default: {DEFAULT_OUT})")
    ap.add_argument("--keep", type=int, default=30,
                    help="how many backups to retain; 0 keeps everything")
    args = ap.parse_args()

    print(f"backing up to {args.out}")
    target = dump(args.out, args.keep)
    size = target.stat().st_size
    print(f"\nwrote {target.name}  ({size:,} bytes / {size/1024/1024:.2f} MB)")
    print("This file contains all your business data — keep it private.")


if __name__ == "__main__":
    main()
