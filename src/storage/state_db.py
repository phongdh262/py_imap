import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.timezone import format_vn_datetime


class StateDatabase:
    """
    SQLite-backed migration state tracking engine:
    - Provides idempotency: prevents duplicate email creation on destination
    - Supports resuming interrupted migrations seamlessly
    - Records detailed success and failure logs for auditing and HTML/CSV reports
    """

    def __init__(self, db_path: str = "data/migration_state.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrent write performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initializes database schema with indexing for fast deduplication lookup."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_account TEXT NOT NULL,
                    dest_account TEXT NOT NULL,
                    status TEXT NOT NULL, -- IN_PROGRESS, COMPLETED, FAILED
                    total_messages INTEGER DEFAULT 0,
                    migrated_messages INTEGER DEFAULT 0,
                    failed_messages INTEGER DEFAULT 0,
                    skipped_messages INTEGER DEFAULT 0,
                    transferred_bytes INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_id INTEGER NOT NULL,
                    source_account TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    source_uid INTEGER NOT NULL,
                    msg_hash TEXT NOT NULL,
                    message_id TEXT,
                    subject TEXT,
                    sender TEXT,
                    date_str TEXT,
                    size_bytes INTEGER DEFAULT 0,
                    status TEXT NOT NULL, -- SUCCESS, FAILED
                    error_code TEXT,
                    error_detail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (migration_id) REFERENCES migrations(id)
                );

                CREATE INDEX IF NOT EXISTS idx_msg_hash 
                ON messages_state (source_account, folder, msg_hash);

                CREATE INDEX IF NOT EXISTS idx_migration_status 
                ON messages_state (migration_id, status);
                """
            )
            conn.commit()

    @staticmethod
    def compute_message_hash(
        message_id: Optional[str], date_str: Optional[str], subject: Optional[str], size: int
    ) -> str:
        """
        Computes a resilient unique signature for an email:
        Uses Message-ID header if available, otherwise falls back to hash(Date + Subject + Size).
        """
        raw_key = f"{message_id or ''}|{date_str or ''}|{subject or ''}|{size}"
        return hashlib.sha256(raw_key.encode("utf-8", errors="ignore")).hexdigest()

    def start_migration(self, source_account: str, dest_account: str, total_messages: int = 0) -> int:
        """Creates a new migration session and returns its ID."""
        now_vn = format_vn_datetime(fmt="%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO migrations (source_account, dest_account, status, total_messages, started_at)
                VALUES (?, ?, 'IN_PROGRESS', ?, ?)
                """,
                (source_account, dest_account, total_messages, now_vn),
            )
            conn.commit()
            return cursor.lastrowid

    def clear_account_state(self, source_account: str):
        """Clears all migration states for an account so it can be re-migrated from scratch."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages_state WHERE source_account = ?", (source_account,))
            conn.commit()

    def is_message_migrated(self, source_account: str, folder: str, msg_hash: str) -> bool:
        """Checks if a message was already successfully migrated to prevent duplication."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM messages_state 
                WHERE source_account = ? AND folder = ? AND msg_hash = ? AND status = 'SUCCESS'
                LIMIT 1
                """,
                (source_account, folder, msg_hash),
            )
            return cursor.fetchone() is not None

    def record_success(
        self,
        migration_id: int,
        source_account: str,
        folder: str,
        source_uid: int,
        msg_hash: str,
        message_id: Optional[str],
        subject: Optional[str],
        sender: Optional[str],
        date_str: Optional[str],
        size_bytes: int,
    ):
        """Records a successfully migrated email."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages_state 
                (migration_id, source_account, folder, source_uid, msg_hash, message_id, subject, sender, date_str, size_bytes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS')
                """,
                (migration_id, source_account, folder, source_uid, msg_hash, message_id, subject, sender, date_str, size_bytes),
            )
            conn.execute(
                """
                UPDATE migrations 
                SET migrated_messages = migrated_messages + 1,
                    transferred_bytes = transferred_bytes + ?
                WHERE id = ?
                """,
                (size_bytes, migration_id),
            )
            conn.commit()

    def record_failure(
        self,
        migration_id: int,
        source_account: str,
        folder: str,
        source_uid: int,
        msg_hash: str,
        message_id: Optional[str],
        subject: Optional[str],
        sender: Optional[str],
        date_str: Optional[str],
        size_bytes: int,
        error_code: str,
        error_detail: str,
    ):
        """Records a failed email migration with exact reason for reporting."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages_state 
                (migration_id, source_account, folder, source_uid, msg_hash, message_id, subject, sender, date_str, size_bytes, status, error_code, error_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FAILED', ?, ?)
                """,
                (migration_id, source_account, folder, source_uid, msg_hash, message_id, subject, sender, date_str, size_bytes, error_code, error_detail),
            )
            conn.execute(
                """
                UPDATE migrations 
                SET failed_messages = failed_messages + 1
                WHERE id = ?
                """,
                (migration_id,),
            )
            conn.commit()

    def record_skipped(self, migration_id: int):
        """Increments skipped counter when an email is detected as already migrated."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE migrations 
                SET skipped_messages = skipped_messages + 1
                WHERE id = ?
                """,
                (migration_id,),
            )
            conn.commit()

    def complete_migration(self, migration_id: int, status: str = "COMPLETED"):
        """Marks migration session as completed."""
        now_vn = format_vn_datetime(fmt="%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE migrations 
                SET status = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, now_vn, migration_id),
            )
            conn.commit()

    def get_migration_summary(self, migration_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves session details and stats."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM migrations WHERE id = ?", (migration_id,)).fetchone()
            return dict(row) if row else None

    def get_failed_messages(self, migration_id: int) -> List[Dict[str, Any]]:
        """Returns all failed messages for a migration session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT folder, source_uid, message_id, subject, sender, date_str, size_bytes, error_code, error_detail
                FROM messages_state
                WHERE migration_id = ? AND status = 'FAILED'
                ORDER BY folder, source_uid
                """,
                (migration_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_folder_statistics(self, migration_id: int) -> List[Dict[str, Any]]:
        """Summarizes progress per folder."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    folder,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                    SUM(size_bytes) as total_size
                FROM messages_state
                WHERE migration_id = ?
                GROUP BY folder
                """,
                (migration_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_migration(self, migration_id: int) -> bool:
        """Deletes a single migration record and its associated message states."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages_state WHERE migration_id = ?", (migration_id,))
            cursor = conn.execute("DELETE FROM migrations WHERE id = ?", (migration_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_migrations(self) -> int:
        """Deletes all migration records and associated message states, then vacuums the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages_state")
            cursor = conn.execute("DELETE FROM migrations")
            count = cursor.rowcount
            conn.commit()
            try:
                conn.execute("VACUUM")
            except Exception:
                pass
            return count

