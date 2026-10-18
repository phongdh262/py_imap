from collections import defaultdict
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.models import AccountCredentials, FolderRole
from src.core.throttler import ProviderThrottler
from src.reports.reporter import MigrationReporter
from src.storage.state_db import StateDatabase
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import MESSAGES_FAILED_TOTAL, MESSAGES_MIGRATED_TOTAL

console = Console()
logger = setup_logging()


class RetryEngine:
    """
    Dedicated Retry Engine for recovering previously failed emails:
    - Queries SQLite State Database for failed records of a specific migration session
    - Groups items by folder and retrieves only the exact missing UIDs
    - Applies throttling & exponential backoff on retries
    - Updates State Database & re-generates HTML/CSV audit reports automatically
    """

    def __init__(self, state_db: StateDatabase, throttler: Optional[ProviderThrottler] = None):
        self.state_db = state_db
        self.throttler = throttler or ProviderThrottler(batch_delay_seconds=0.1)
        self.reporter = MigrationReporter(self.state_db)

    def list_failed_sessions(self) -> List[Dict]:
        """Lists all migration sessions that have failed messages."""
        with self.state_db._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, source_account, dest_account, status, total_messages, migrated_messages, failed_messages, started_at
                FROM migrations
                WHERE failed_messages > 0
                ORDER BY id DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def retry_session(
        self,
        migration_id: int,
        src_creds: AccountCredentials,
        dst_creds: AccountCredentials,
    ) -> Dict[str, int]:
        """Executes targeted retry for failed items in a migration session."""
        failed_items = self.state_db.get_failed_messages(migration_id)
        if not failed_items:
            console.print(f"[bold green]Phiên #{migration_id} không có thư nào bị lỗi![/bold green]")
            return {"recovered": 0, "still_failed": 0}

        console.print(
            Panel.fit(
                f"[bold yellow]Bắt Đầu Thử Lại (Retry) Thư Lỗi Cho Phiên #{migration_id}[/bold yellow]\n"
                f"Tổng số thư cần thử lại: [bold red]{len(failed_items)}[/bold red] thư\n"
                f"Tài khoản: [cyan]{src_creds.username}[/cyan] ➔ [magenta]{dst_creds.username}[/magenta]",
                border_style="yellow",
            )
        )

        # Group failed items by folder: {folder: [item, ...]}
        folder_groups = defaultdict(list)
        for item in failed_items:
            folder_groups[item["folder"]].append(item)

        recovered_count = 0
        still_failed_count = 0

        with IMAPClientWrapper(src_creds) as src_client, IMAPClientWrapper(dst_creds) as dst_client:
            # Detect destination namespace and folders
            dst_folders = dst_client.client.list_folders()
            dst_canonical_map: Dict[FolderRole, str] = {}
            dest_delim = "/"
            dest_prefix = ""

            try:
                ns = dst_client.client.namespace()
                if ns and ns.personal and len(ns.personal) > 0:
                    dest_prefix = ns.personal[0][0] or ""
            except Exception:
                dest_prefix = ""

            mapper = FolderMapper()
            for flags, delimiter, raw_name in dst_folders:
                dest_delim = delimiter.decode("latin-1") if isinstance(delimiter, bytes) else str(delimiter)
                folder_name = mapper.decode_folder_name(raw_name)
                role = mapper.identify_role(folder_name, flags)
                if role != FolderRole.CUSTOM and role not in dst_canonical_map:
                    dst_canonical_map[role] = folder_name
                if not dest_prefix:
                    if folder_name.startswith("INBOX."):
                        dest_prefix = "INBOX."
                    elif folder_name.startswith("INBOX/"):
                        dest_prefix = "INBOX/"

            def ensure_dst_folder(fname: str) -> str:
                if fname.upper() == "INBOX":
                    return "INBOX"
                try:
                    if not dst_client.client.folder_exists(fname):
                        dst_client.client.create_folder(fname)
                    return fname
                except Exception as ex:
                    msg = str(ex).lower()
                    if "nonexistent namespace" in msg or "prefixed with: inbox" in msg:
                        pfx = "INBOX." if ("." in fname or "/" not in fname) else "INBOX/"
                        fb = fname if fname.startswith(pfx) else f"{pfx}{fname}"
                        try:
                            if not dst_client.client.folder_exists(fb):
                                dst_client.client.create_folder(fb)
                            return fb
                        except Exception:
                            pass
                    return fname

            for folder, items in folder_groups.items():
                target_folder = mapper.map_folder_name(
                    source_folder=folder,
                    source_role=mapper.identify_role(folder, []),
                    source_delim="/",
                    dest_delim=dest_delim,
                    dest_canonical_map=dst_canonical_map,
                    dest_prefix=dest_prefix,
                )
                target_folder = ensure_dst_folder(target_folder)

                console.print(f"🔄 Đang thử lại [cyan]{len(items)}[/cyan] thư: [yellow]{folder}[/yellow] ➔ [green]{target_folder}[/green]...")

                try:
                    src_client.client.select_folder(folder, readonly=True)
                except Exception as e:
                    console.print(f"[bold red]Không thể chọn thư mục nguồn {folder}: {e}[/bold red]")
                    still_failed_count += len(items)
                    continue

                for item in items:
                    uid = item["source_uid"]
                    self.throttler.throttle_batch()

                    try:
                        fetch_res = src_client.client.fetch([uid], ["RFC822", "FLAGS", "INTERNALDATE", "RFC822.SIZE"])
                        msg_data = fetch_res.get(uid)

                        if not msg_data or not msg_data.get(b"RFC822"):
                            still_failed_count += 1
                            continue

                        raw_body = msg_data[b"RFC822"]
                        flags = [f for f in msg_data.get(b"FLAGS", ()) if f.lower() not in (b"\\recent",)]
                        internal_date = msg_data.get(b"INTERNALDATE")
                        size = msg_data.get(b"RFC822.SIZE", len(raw_body))

                        # Upload to destination with self-healing namespace
                        try:
                            dst_client.client.append(target_folder, raw_body, flags=flags, msg_time=internal_date)
                        except Exception as app_ex:
                            app_err = str(app_ex).lower()
                            if "nonexistent namespace" in app_err or "prefixed with: inbox" in app_err:
                                pfx = "INBOX." if ("." in target_folder or "/" not in target_folder) else "INBOX/"
                                fb = target_folder if target_folder.startswith(pfx) else f"{pfx}{target_folder}"
                                target_folder = ensure_dst_folder(fb)
                                dst_client.client.append(target_folder, raw_body, flags=flags, msg_time=internal_date)
                            else:
                                raise app_ex

                        # Update State DB: from FAILED to SUCCESS
                        self._mark_item_recovered(migration_id, item["folder"], uid, size)
                        recovered_count += 1
                        MESSAGES_MIGRATED_TOTAL.labels(source_account=src_creds.username, folder=folder).inc()

                    except Exception as e:
                        still_failed_count += 1
                        err_str = str(e)
                        if self.throttler.is_throttled_error(err_str):
                            self.throttler.wait_backoff(1, src_creds.username, dst_creds.host, err_str)

        # Re-generate updated HTML & CSV reports
        html_report, csv_report = self.reporter.generate_reports(migration_id)

        console.print(
            Panel.fit(
                f"[bold green]✓ Hoàn Tất Thử Lại (Retry Session #{migration_id})[/bold green]\n"
                f"Đã phục hồi thành công: [bold green]{recovered_count}[/bold green] thư\n"
                f"Vẫn còn lỗi: [bold red]{still_failed_count}[/bold red] thư\n\n"
                f"Báo cáo HTML mới: [cyan]{html_report.resolve()}[/cyan]"
                + (f"\nDanh sách lỗi còn lại: [red]{csv_report.resolve()}[/red]" if csv_report else ""),
                border_style="green",
            )
        )

        return {"recovered": recovered_count, "still_failed": still_failed_count}

    def _mark_item_recovered(self, migration_id: int, folder: str, uid: int, size_bytes: int):
        """Updates database record from FAILED to SUCCESS."""
        with self.state_db._get_connection() as conn:
            conn.execute(
                """
                UPDATE messages_state
                SET status = 'SUCCESS', error_code = NULL, error_detail = NULL
                WHERE migration_id = ? AND folder = ? AND source_uid = ?
                """,
                (migration_id, folder, uid),
            )
            conn.execute(
                """
                UPDATE migrations
                SET migrated_messages = migrated_messages + 1,
                    failed_messages = MAX(0, failed_messages - 1),
                    transferred_bytes = transferred_bytes + ?
                WHERE id = ?
                """,
                (size_bytes, migration_id),
            )
            conn.commit()
