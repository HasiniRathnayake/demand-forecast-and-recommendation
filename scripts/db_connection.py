# scripts/db_connection.py
import os
import psycopg2
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class DatabaseConnection:
    _connection_error_reported = False

    def __init__(self):
        self.conn = None
        self.cur = None

    def connect(self):
        db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
        if not db_url:
            if not DatabaseConnection._connection_error_reported:
                print("Connection error: DATABASE_URL (or SUPABASE_DB_URL) is not set")
                DatabaseConnection._connection_error_reported = True
            return None, None

        if db_url.startswith("http://") or db_url.startswith("https://"):
            if not DatabaseConnection._connection_error_reported:
                print(
                    "Connection error: DATABASE_URL must be a PostgreSQL DSN (postgresql://...), "
                    "not the Supabase API URL. Keep SUPABASE_URL for API calls and set "
                    "DATABASE_URL/SUPABASE_DB_URL to the Supabase Postgres connection string."
                )
                DatabaseConnection._connection_error_reported = True
            return None, None

        if "supabase.co" in db_url and "sslmode=" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{sep}sslmode=require"

        try:
            self.conn = psycopg2.connect(
                db_url,
                connect_timeout=30
            )
            self.cur = self.conn.cursor()
            DatabaseConnection._connection_error_reported = False
            return self.conn, self.cur
        except Exception as e:
            if not DatabaseConnection._connection_error_reported:
                print(f"Connection error: {e}")
                DatabaseConnection._connection_error_reported = True
            return None, None

    def fetch_all(self, query, params=None):
        try:
            conn, cur = self.connect()
            if not conn or not cur:
                return []
            self.cur.execute(query, params or ())
            result = self.cur.fetchall()
            self.disconnect()
            return result if result else []
        except Exception as e:
            print(f"Fetch error: {e}")
            self.disconnect()
            return []

    def fetch_one(self, query, params=None):
        try:
            conn, cur = self.connect()
            if not conn or not cur:
                return None
            self.cur.execute(query, params or ())
            result = self.cur.fetchone()
            self.disconnect()
            return result if result else None
        except Exception as e:
            print(f"Fetch error: {e}")
            self.disconnect()
            return None

    def execute_query(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE"""
        try:
            self.connect()
            if self.cur and self.conn:
                self.cur.execute(query, params or ())
                self.conn.commit()
                self.disconnect()
                return True
            return False
        except Exception as e:
            print(f"Execute error: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
            self.disconnect()
            return False

    def disconnect(self):
        try:
            if self.cur:
                self.cur.close()
            if self.conn:
                self.conn.close()
        except:
            pass