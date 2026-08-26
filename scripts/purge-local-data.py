#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "backend" / "instance" / "xultron.sqlite3"
TABLES = (
    "messages",
    "conversations",
    "memory_items",
    "idempotency_keys",
    "sessions",
    "device_commands",
    "device_events",
    "devices",
)
DELETE_ORDER = (
    "messages",
    "idempotency_keys",
    "memory_items",
    "conversations",
    "device_commands",
    "device_events",
    "devices",
    "sessions",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Permanently erase local conversational and activity data.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--yes", action="store_true", help="Confirm permanent deletion")
    args = parser.parse_args()
    if not args.yes:
        parser.error("permanent deletion requires --yes")
    if not args.database.is_file():
        parser.error(f"database not found: {args.database}")

    connection = sqlite3.connect(args.database)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA secure_delete=ON")
    existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    before = {table: count(connection, table) for table in TABLES if table in existing}
    before["guest_users"] = count_where(connection, "users", "is_guest = 1") if "users" in existing else 0
    with connection:
        for table in DELETE_ORDER:
            if table in existing:
                connection.execute(f"DELETE FROM {table}")
        if "users" in existing:
            connection.execute("DELETE FROM users WHERE is_guest = 1")
    connection.execute("VACUUM")
    after = {table: count(connection, table) for table in TABLES if table in existing}
    after["guest_users"] = count_where(connection, "users", "is_guest = 1") if "users" in existing else 0
    connection.close()
    for suffix in ("-wal", "-shm"):
        Path(str(args.database) + suffix).unlink(missing_ok=True)
    print(json.dumps({"before": before, "after": after}, indent=2))
    if any(after.values()):
        raise SystemExit("purge did not remove every targeted record")


def count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def count_where(connection: sqlite3.Connection, table: str, where: str) -> int:
    return connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


if __name__ == "__main__":
    main()
