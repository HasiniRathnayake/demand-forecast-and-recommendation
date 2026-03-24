"""
One-way sync utility: Supabase -> local PostgreSQL.

Usage:
  python scripts/sync_supabase_to_postgres.py
  python scripts/sync_supabase_to_postgres.py --full

Environment variables required:
  SUPABASE_URL
  SUPABASE_KEY
  DATABASE_URL

Notes:
  - This tool syncs configured tables only.
  - Incremental mode uses `updated_at` when available.
  - Full mode (`--full`) fetches all rows and upserts into Postgres.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client
import psycopg2
from psycopg2.extras import Json, execute_values


load_dotenv()


SYNC_STATE_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    table_name TEXT PRIMARY KEY,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01T00:00:00Z'
);
"""


TABLE_CONFIG: dict[str, dict[str, str]] = {
    "users": {"pk": "user_id", "updated_col": "created_at"},
    "product_catalog": {"pk": "product_code", "updated_col": "created_at"},
    "demand_forecasts": {"pk": "forecast_id", "updated_col": "created_at"},
    "inventory_intake_log": {"pk": "intake_id", "updated_col": "created_at"},
    "suppliers": {"pk": "supplier_id", "updated_col": "created_at"},
}


def ensure_env() -> tuple[str, str, str]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_KEY")
    if not database_url:
        missing.append("DATABASE_URL")

    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    return supabase_url, supabase_key, database_url


def get_last_sync(cur, table_name: str) -> datetime:
    cur.execute("SELECT last_synced_at FROM sync_state WHERE table_name = %s", (table_name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("INSERT INTO sync_state(table_name) VALUES (%s)", (table_name,))
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def set_last_sync(cur, table_name: str, ts: datetime) -> None:
    cur.execute(
        "UPDATE sync_state SET last_synced_at = %s WHERE table_name = %s",
        (ts, table_name),
    )


def fetch_supabase_rows(
    sb: Client,
    table_name: str,
    updated_col: str,
    since_ts: datetime,
    full_refresh: bool,
) -> list[dict[str, Any]]:
    query = sb.table(table_name).select("*")

    if not full_refresh:
        try:
            query = query.gt(updated_col, since_ts.isoformat()).order(updated_col)
            response = query.limit(10000).execute()
        except Exception as e:
            # If updated_col filtering fails (e.g., column doesn't exist), fallback to full pull.
            print(f"  Note: {table_name} filtering failed ({str(e)[:80]}...), falling back to full pull.")
            query = sb.table(table_name).select("*")
            response = query.limit(10000).execute()
    else:
        response = query.limit(10000).execute()

    return response.data or []


def get_postgres_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def upsert_rows(
    cur,
    table_name: str,
    pk_col: str,
    rows: list[dict[str, Any]],
    updated_col: str,
) -> datetime | None:
    if not rows:
        return None

    table_cols = get_postgres_columns(cur, table_name)
    if not table_cols:
        raise RuntimeError(f"Target Postgres table missing: {table_name}")

    usable_cols = [c for c in rows[0].keys() if c in table_cols]
    if pk_col not in usable_cols:
        raise RuntimeError(f"Primary key '{pk_col}' missing from target table '{table_name}'")

    def _adapt_value(value: Any) -> Any:
        # Supabase rows often include nested objects/arrays; map them to JSON.
        if isinstance(value, (dict, list)):
            return Json(value)
        return value

    values = [[_adapt_value(row.get(col)) for col in usable_cols] for row in rows]
    insert_cols = ", ".join(usable_cols)
    update_cols = ", ".join(f"{c} = EXCLUDED.{c}" for c in usable_cols if c != pk_col)

    if update_cols:
        sql = (
            f"INSERT INTO {table_name} ({insert_cols}) VALUES %s "
            f"ON CONFLICT ({pk_col}) DO UPDATE SET {update_cols}"
        )
    else:
        sql = f"INSERT INTO {table_name} ({insert_cols}) VALUES %s ON CONFLICT ({pk_col}) DO NOTHING"

    execute_values(cur, sql, values)

    if updated_col in usable_cols:
        updated_values = [r.get(updated_col) for r in rows if r.get(updated_col)]
        if updated_values:
            latest = max(updated_values)
            if isinstance(latest, str):
                return datetime.fromisoformat(latest.replace("Z", "+00:00"))
            if isinstance(latest, datetime):
                return latest

    return datetime.now(timezone.utc)


def run_sync(full_refresh: bool) -> None:
    supabase_url, supabase_key, database_url = ensure_env()
    sb = create_client(supabase_url, supabase_key)
    conn = psycopg2.connect(database_url)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SYNC_STATE_SQL)

                for table_name, cfg in TABLE_CONFIG.items():
                    pk_col = cfg["pk"]
                    updated_col = cfg.get("updated_col", "updated_at")

                    since_ts = get_last_sync(cur, table_name)
                    rows = fetch_supabase_rows(sb, table_name, updated_col, since_ts, full_refresh)

                    latest = upsert_rows(cur, table_name, pk_col, rows, updated_col) if rows else None
                    if latest:
                        set_last_sync(cur, table_name, latest)

                    print(f"{table_name}: synced {len(rows)} row(s)")

        print("Sync completed successfully.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Supabase tables into local PostgreSQL")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full refresh (ignore sync_state timestamps)",
    )
    args = parser.parse_args()

    run_sync(full_refresh=args.full)


if __name__ == "__main__":
    main()
