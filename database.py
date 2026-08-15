import sqlite3
import datetime
import os

DB_FILE = "bot_data.db"

class Database:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Dynamic settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    txid TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount_ltc REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'verified'
                )
            """)

            # Active temporary role access table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    granted_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)

            conn.commit()

    # Dynamic Settings Helpers
    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def get_setting(self, key: str, default=None):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    # Payment & TXID Operations
    def is_txid_used(self, txid: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM payments WHERE LOWER(txid) = LOWER(?)", (txid.strip(),))
            return cursor.fetchone() is not None

    def record_payment(self, txid: str, user_id: int, amount_ltc: float):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO payments (txid, user_id, amount_ltc) VALUES (?, ?, ?)",
                (txid.strip().lower(), user_id, amount_ltc)
            )
            conn.commit()

    # Role Access & Timer Operations
    def grant_role_access(self, user_id: int, guild_id: int, role_id: int, duration_hours: float):
        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(hours=duration_hours)
        
        with self.get_connection() as conn:
            # Revoke existing active entries for this user & role if any
            conn.execute(
                "UPDATE active_roles SET status = 'superseded' WHERE user_id = ? AND role_id = ? AND status = 'active'",
                (user_id, role_id)
            )
            conn.execute(
                """
                INSERT INTO active_roles (user_id, guild_id, role_id, granted_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (user_id, guild_id, role_id, now.isoformat(), expires_at.isoformat())
            )
            conn.commit()
        return expires_at

    def get_expired_roles(self):
        now_str = datetime.datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM active_roles WHERE status = 'active' AND expires_at <= ?",
                (now_str,)
            )
            return cursor.fetchall()

    def mark_role_expired(self, record_id: int):
        with self.get_connection() as conn:
            conn.execute("UPDATE active_roles SET status = 'expired' WHERE id = ?", (record_id,))
            conn.commit()

    def revoke_user_access(self, user_id: int, role_id: int):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE active_roles SET status = 'revoked' WHERE user_id = ? AND role_id = ? AND status = 'active'",
                (user_id, role_id)
            )
            conn.commit()

    def get_active_user_access(self, user_id: int, role_id: int):
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM active_roles WHERE user_id = ? AND role_id = ? AND status = 'active'",
                (user_id, role_id)
            )
            return cursor.fetchone()

db = Database()
