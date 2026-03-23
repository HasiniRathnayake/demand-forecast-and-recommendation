# scripts/db_connection.py
import os
import psycopg2
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class DatabaseConnection:
    def __init__(self):
        self.conn = None
        self.cur = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                os.getenv("DATABASE_URL"),
                connect_timeout=30
            )
            self.cur = self.conn.cursor()
            return self.conn, self.cur
        except Exception as e:
            print(f"Connection error: {e}")
            return None, None

    def fetch_all(self, query, params=None):
        try:
            self.connect()
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
            self.connect()
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