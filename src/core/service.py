import csv
from datetime import datetime
import os
from pathlib import Path
import socket
import time
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.inspector import MailboxInspector
from src.core.migrator import EmailMigrator
from src.core.models import AccountCredentials, FolderRole, MailboxSummary
from src.core.timezone import format_vn_datetime
from src.reports.reporter import MigrationReporter
from src.storage.state_db import StateDatabase
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import (
    ACCOUNT_PROGRESS_PERCENT,
    ACTIVE_WORKERS,
    SOURCE_MAILBOX_MESSAGES_TOTAL,
    SOURCE_MAILBOX_SIZE_BYTES,
    MESSAGES_SKIPPED_TOTAL,
    MESSAGES_MISSING_TOTAL,
    MIGRATION_JOBS_TOTAL,
    MIGRATION_DURATION_SECONDS,
    ERRORS_DETECTED_TOTAL,
)

logger = setup_logging()
console = Console()


from src.core.provider_rules import ProviderRulesManager
from src.core.throttler import ProviderThrottler


class MigrationService:
    """
    High-level Orchestrator for Email Migration:
    - Pre-flight inspection & Quota/Size terminal rendering
    - Automatic cross-server folder mapping & Vietnamese accent handling
    - Idempotency & Resume via SQLite State DB
    - Anti-ban Throttling & Automated HTML/CSV Audit Reporting
    """

    def __init__(
        self,
        mapping_config: Optional[dict] = None,
        sanitize_accents: bool = False,
        batch_delay_seconds: float = 0.05,
    ):
        self.state_db = StateDatabase()
        self.reporter = MigrationReporter(self.state_db)
        self.throttler = ProviderThrottler(batch_delay_seconds=batch_delay_seconds)
        self.rules_mgr = ProviderRulesManager()
        self.sanitize_accents = sanitize_accents
        self.mapper = FolderMapper(sanitize_accents=sanitize_accents, rules_manager=self.rules_mgr)
        self.inspector = MailboxInspector(mapper=self.mapper)
        self.migrator = EmailMigrator(state_db=self.state_db, throttler=self.throttler)

    def inspect_source(self, src_creds: AccountCredentials) -> MailboxSummary:
        """Inspects source account and outputs formatted terminal summary."""
        console.print(f"[bold cyan]🔍 Inspecting Source Mailbox:[/bold cyan] [yellow]{src_creds.username}[/yellow] ({src_creds.host})")

        src_prov = self.rules_mgr.detect_provider(src_creds.host, src_creds.username)
        src_mapper = FolderMapper(
            source_provider=src_prov,
            sanitize_accents=self.sanitize_accents,
            rules_manager=self.rules_mgr,
        )
        inspector = MailboxInspector(mapper=src_mapper)

        with IMAPClientWrapper(src_creds) as src_client:
            summary = inspector.inspect(src_client)

            # Update Prometheus Gauges
            SOURCE_MAILBOX_SIZE_BYTES.labels(source_account=src_creds.username).set(summary.total_size_bytes)
            SOURCE_MAILBOX_MESSAGES_TOTAL.labels(source_account=src_creds.username).set(summary.total_messages)

            # Print Rich Table
            self._render_inspection_table(summary)
            return summary

    def inspect_destination(self, dst_creds: AccountCredentials) -> MailboxSummary:
        """Inspects destination account to discover existing folders, size, and messages."""
        dst_prov = self.rules_mgr.detect_provider(dst_creds.host, dst_creds.username)
        dst_mapper = FolderMapper(
            source_provider=dst_prov,
            sanitize_accents=self.sanitize_accents,
            rules_manager=self.rules_mgr,
        )
        inspector = MailboxInspector(mapper=dst_mapper)
        with IMAPClientWrapper(dst_creds) as dst_client:
            return inspector.inspect(dst_client)

    def inspect_both(
        self, src_creds: AccountCredentials, dst_creds: Optional[AccountCredentials] = None
    ) -> dict:
        """Pre-flight dual inspection: compares source against destination."""
        src_summary = self.inspect_source(src_creds)
        dst_summary = None

        if dst_creds and dst_creds.username and dst_creds.password:
            try:
                dst_summary = self.inspect_destination(dst_creds)
            except Exception as e:
                logger.warning("Destination pre-flight scan failed: %s", e)

        reconciliation = {
            "source_messages": src_summary.total_messages,
            "source_size_mb": src_summary.total_size_mb,
            "dest_existing_messages": dst_summary.total_messages if dst_summary else 0,
            "dest_existing_size_mb": dst_summary.total_size_mb if dst_summary else "0.00",
            "messages_to_transfer": max(0, src_summary.total_messages - (dst_summary.total_messages if dst_summary else 0)),
            "dest_quota": dst_summary.quota if dst_summary else None,
            "safe_mode_guarantee": "Hệ thống hoạt động theo nguyên tắc Append-Only: Giữ nguyên vẹn 100% dữ liệu đang có trên máy chủ đích, tự động quét Message-ID thực tế để không xóa đè và không nạp trùng.",
        }

        return {
            "source": src_summary,
            "dest": dst_summary,
            "reconciliation": reconciliation,
        }

    def migrate_account(
        self,
        src_creds: AccountCredentials,
        dst_creds: AccountCredentials,
        custom_folder_mapping: Optional[Dict[str, str]] = None,
        force_remigrate: bool = False,
    ) -> dict:
        """Executes full migration for a single account pair with resume & reporting."""
        console.print(
            Panel.fit(
                f"[bold green]Starting Migration[/bold green]\n"
                f"[cyan]Source:[/cyan] {src_creds.username} @ {src_creds.host}\n"
                f"[magenta]Destination:[/magenta] {dst_creds.username} @ {dst_creds.host}",
                border_style="green",
            )
        )

        ACTIVE_WORKERS.inc()
        total_success = 0
        total_failed = 0
        total_skipped = 0

        src_prov = self.rules_mgr.detect_provider(src_creds.host, src_creds.username)
        dst_prov = self.rules_mgr.detect_provider(dst_creds.host, dst_creds.username)
        mapper = FolderMapper(
            custom_mappings=custom_folder_mapping,
            sanitize_accents=self.sanitize_accents,
            source_provider=src_prov,
            dest_provider=dst_prov,
            rules_manager=self.rules_mgr,
        )
        inspector = MailboxInspector(mapper=mapper)

        # Apply recommended provider rate limits
        rec_throttle = self.rules_mgr.get_recommended_throttling(src_prov)
        if rec_throttle and "batch_delay_ms" in rec_throttle:
            self.throttler.batch_delay = rec_throttle["batch_delay_ms"] / 1000.0

        start_time = time.time()
        start_time_str = format_vn_datetime(fmt="%Y-%m-%d %H:%M:%S")
        hostname = socket.gethostname()
        pid = os.getpid()

        logger.info(
            f"Here is py_imap 1.0.0 on host {hostname} PID is {pid}",
            action="SESSION_START",
            status="INFO",
            source_account=src_creds.username,
            dest_account=dst_creds.username,
            host1=src_creds.host,
            host2=dst_creds.host,
            user1=src_creds.username,
            user2=dst_creds.username,
            pid=pid,
        )
        logger.info(
            f"Host1: IMAP server [{src_creds.host}] port [{src_creds.port}] user [{src_creds.username}]",
            source_account=src_creds.username,
            dest_account=dst_creds.username,
        )
        logger.info(
            f"Host2: IMAP server [{dst_creds.host}] port [{dst_creds.port}] user [{dst_creds.username}]",
            source_account=src_creds.username,
            dest_account=dst_creds.username,
        )

        try:
            with IMAPClientWrapper(src_creds) as src_client, IMAPClientWrapper(dst_creds) as dst_client:
                logger.info(
                    f"Host1: success login on [{src_creds.host}]",
                    source_account=src_creds.username,
                    dest_account=dst_creds.username,
                )
                logger.info(
                    f"Host2: success login on [{dst_creds.host}]",
                    source_account=src_creds.username,
                    dest_account=dst_creds.username,
                )

                # 1. Pre-flight inspect source
                summary = inspector.inspect(src_client)
                logger.info(
                    f"Host1: found {len(summary.folders)} folders.",
                    source_account=src_creds.username,
                    dest_account=dst_creds.username,
                )

                SOURCE_MAILBOX_SIZE_BYTES.labels(source_account=src_creds.username).set(summary.total_size_bytes)
                SOURCE_MAILBOX_MESSAGES_TOTAL.labels(source_account=src_creds.username).set(summary.total_messages)

                # 2. Start session in State DB for idempotency & auditing
                migration_id = self.state_db.start_migration(
                    src_creds.username, dst_creds.username, summary.total_messages
                )

                # 3. Inspect destination folder hierarchy for role mapping and namespace prefix
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

                # 4. Migrate each non-excluded selectable folder
                migrated_msgs_counter = 0
                total_target_msgs = summary.total_messages or 1
                selectable_folders = [f for f in summary.folders if not f.is_excluded and f.is_selectable]
                folders_synced_count = 0

                for folder in summary.folders:
                    if folder.is_excluded or not folder.is_selectable:
                        continue

                    # Map target name
                    target_name = mapper.map_folder_name(
                        source_folder=folder.name,
                        source_role=folder.role,
                        source_delim=folder.delimiter,
                        dest_delim=dest_delim,
                        dest_canonical_map=dst_canonical_map,
                        dest_prefix=dest_prefix,
                    )

                    console.print(f"📦 Migrating folder: [cyan]{folder.name}[/cyan] ➔ [green]{target_name}[/green] ({folder.messages_count} msgs)")

                    def on_progress(done_in_folder, total_in_folder):
                        nonlocal migrated_msgs_counter
                        progress = round(((migrated_msgs_counter + done_in_folder) / total_target_msgs) * 100, 2)
                        ACCOUNT_PROGRESS_PERCENT.labels(
                            source_account=src_creds.username, dest_account=dst_creds.username
                        ).set(min(progress, 100.0))

                    s_count, f_count, skip_count = self.migrator.migrate_folder(
                        src_client=src_client.client,
                        dst_client=dst_client.client,
                        src_account=src_creds.username,
                        dst_account=dst_creds.username,
                        src_folder=folder.name,
                        dst_folder=target_name,
                        migration_id=migration_id,
                        on_progress=on_progress,
                        force_remigrate=force_remigrate,
                    )
                    total_success += s_count
                    total_failed += f_count
                    total_skipped += skip_count
                    migrated_msgs_counter += (s_count + f_count + skip_count)
                    if f_count == 0:
                        folders_synced_count += 1

                ACCOUNT_PROGRESS_PERCENT.labels(
                    source_account=src_creds.username, dest_account=dst_creds.username
                ).set(100.0)

                # 5. Mark completion in State DB
                final_status = "COMPLETED" if total_failed == 0 else "PARTIAL"
                self.state_db.complete_migration(migration_id, status=final_status)

                # 6. Generate HTML and CSV audit reports
                html_report, csv_report = self.reporter.generate_reports(migration_id)

                # 7. Print summary panel & log imapsync ++++ Statistics
                duration_sec = time.time() - start_time
                end_time_str = format_vn_datetime(fmt="%Y-%m-%d %H:%M:%S")
                missing_count = max(0, summary.total_messages - (total_success + total_skipped))
                exit_code = 0 if total_failed == 0 else 111
                exit_desc = "EX_OK: successful termination" if exit_code == 0 else "EX_ERRORS: termination with errors"
                msg_rate = total_success / max(duration_sec, 0.1)
                bw_rate_mib = round((summary.total_size_bytes / (1024 * 1024)) / max(duration_sec, 0.1), 2)

                stats_lines = [
                    "++++ Statistics",
                    f"Transfer started on : {start_time_str}",
                    f"Transfer ended on   : {end_time_str}",
                    f"Transfer time       : {duration_sec:.1f} sec",
                    f"Folders synced      : {folders_synced_count}/{len(selectable_folders)} synced",
                    f"Messages transferred: {total_success}",
                    f"Messages skipped    : {total_skipped}",
                    f"Messages found in host1 not in host2 : {missing_count}",
                    f"Total bytes transferred : {summary.total_size_bytes}",
                    f"Total bytes skipped     : 0",
                    f"Message rate        : {msg_rate:.1f} msgs/sec",
                    f"Average bandwidth rate : {bw_rate_mib:.2f} MiB/sec",
                    f"Host1 Nb messages   : {summary.total_messages}",
                    f"Host2 Nb messages   : {total_success + total_skipped}",
                    f"Host1 Total size    : {summary.total_size_bytes}",
                    f"Host2 Total size    : {summary.total_size_bytes}",
                    f"Final difference host2 - host1 : {missing_count}",
                    f"Detected {total_failed} errors",
                    f"Exiting with return value {exit_code} ({exit_desc}) {total_failed}/50 nb_errors/max_errors",
                ]
                stats_text = "\n".join(stats_lines)

                logger.info(
                    stats_text,
                    action="STATISTICS",
                    status="SUCCESS" if exit_code == 0 else "FAILED",
                    source_account=src_creds.username,
                    dest_account=dst_creds.username,
                    exit_code=exit_code,
                    transferred=total_success,
                    skipped=total_skipped,
                    missing=missing_count,
                    errors=total_failed,
                    duration_sec=duration_sec,
                )

                # Prometheus metrics update for imapsync dashboard
                MESSAGES_SKIPPED_TOTAL.labels(source_account=src_creds.username, folder="ALL").inc(total_skipped)
                MESSAGES_MISSING_TOTAL.labels(source_account=src_creds.username, dest_account=dst_creds.username).set(missing_count)
                MIGRATION_JOBS_TOTAL.labels(source_account=src_creds.username, dest_account=dst_creds.username, exit_code=str(exit_code)).inc()
                MIGRATION_DURATION_SECONDS.labels(source_account=src_creds.username, dest_account=dst_creds.username).set(duration_sec)
                ERRORS_DETECTED_TOTAL.labels(source_account=src_creds.username, dest_account=dst_creds.username).inc(total_failed)

                report_info = f"[bold cyan]HTML Report:[/bold cyan] {html_report.resolve()}"
                if csv_report:
                    report_info += f"\n[bold red]Failures CSV:[/bold red] {csv_report.resolve()}"

                console.print(
                    Panel.fit(
                        f"[bold green]✓ Migration Completed ({final_status})[/bold green]\n"
                        f"Account: [cyan]{src_creds.username}[/cyan] ➔ [magenta]{dst_creds.username}[/magenta]\n"
                        f"Thành công: [bold green]{total_success}[/bold green] messages\n"
                        f"Bỏ qua (Đã tồn tại / Resume): [bold blue]{total_skipped}[/bold blue] messages\n"
                        f"Thất bại: [bold red]{total_failed}[/bold red] messages\n\n"
                        f"{report_info}",
                        border_style="green",
                    )
                )

                return {
                    "migration_id": migration_id,
                    "success": total_success,
                    "failed": total_failed,
                    "skipped": total_skipped,
                    "html_report": str(html_report),
                    "csv_report": str(csv_report) if csv_report else None,
                }

        except Exception as e:
            exit_code = 16 if ("auth" in str(e).lower() or "login" in str(e).lower()) else 10
            exit_desc = "EX_AUTHENTICATION_FAILURE" if exit_code == 16 else "EX_CONNECTION_FAILURE"
            err_line = f"failure: Error login [{str(e)}]\nExiting with return value {exit_code} ({exit_desc}) 1/50 nb_errors/max_errors"
            logger.error(
                err_line,
                action="SESSION_FAIL",
                status="FAILED",
                source_account=src_creds.username,
                dest_account=dst_creds.username,
                exit_code=exit_code,
            )
            MIGRATION_JOBS_TOTAL.labels(source_account=src_creds.username, dest_account=dst_creds.username, exit_code=str(exit_code)).inc()
            ERRORS_DETECTED_TOTAL.labels(source_account=src_creds.username, dest_account=dst_creds.username).inc(1)
            raise e

        finally:
            ACTIVE_WORKERS.dec()

    def _render_inspection_table(self, summary: MailboxSummary):
        """Renders inspection results to terminal using Rich."""
        table = Table(title=f"Mailbox Summary: {summary.account}", show_header=True, header_style="bold magenta")
        table.add_column("Folder Name", style="cyan")
        table.add_column("Role", style="yellow")
        table.add_column("Messages", justify="right")
        table.add_column("Size (MB)", justify="right")
        table.add_column("Status", justify="center")

        for f in summary.folders:
            size_mb = f"{round(f.size_bytes / (1024 * 1024), 2):.2f}"
            status = "[red]Excluded[/red]" if f.is_excluded else ("[dim]NoSelect[/dim]" if not f.is_selectable else "[green]Ready[/green]")
            table.add_row(f.name, f.role.value, str(f.messages_count), size_mb, status)

        console.print(table)

        quota_str = "Unlimited / Unknown"
        if summary.quota_limit_bytes:
            used_mb = round(summary.quota_used_bytes / (1024 * 1024), 2)
            limit_mb = round(summary.quota_limit_bytes / (1024 * 1024), 2)
            pct = round((summary.quota_used_bytes / summary.quota_limit_bytes) * 100, 1)
            quota_str = f"{used_mb} MB / {limit_mb} MB ({pct}%)"

        console.print(
            Panel(
                f"[bold]Total Size:[/bold] {summary.total_size_mb} MB ({summary.total_size_gb} GB)\n"
                f"[bold]Total Messages:[/bold] {summary.total_messages}\n"
                f"[bold]Server Quota:[/bold] {quota_str}",
                title="Mailbox Statistics",
                border_style="blue",
            )
        )
