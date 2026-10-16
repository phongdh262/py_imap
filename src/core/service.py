import csv
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.inspector import MailboxInspector
from src.core.migrator import EmailMigrator
from src.core.models import AccountCredentials, FolderRole, MailboxSummary
from src.reports.reporter import MigrationReporter
from src.storage.state_db import StateDatabase
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import (
    ACCOUNT_PROGRESS_PERCENT,
    ACTIVE_WORKERS,
    SOURCE_MAILBOX_MESSAGES_TOTAL,
    SOURCE_MAILBOX_SIZE_BYTES,
)

logger = setup_logging()
console = Console()


class MigrationService:
    """
    High-level Orchestrator for Email Migration:
    - Pre-flight inspection & Quota/Size terminal rendering
    - Automatic cross-server folder mapping
    - Idempotency & Resume via SQLite State DB
    - Telemetry & Automated HTML/CSV Audit Reporting
    """

    def __init__(self, mapping_config: Optional[dict] = None):
        self.state_db = StateDatabase()
        self.reporter = MigrationReporter(self.state_db)
        self.mapper = FolderMapper()
        self.inspector = MailboxInspector(mapper=self.mapper)
        self.migrator = EmailMigrator(state_db=self.state_db)

    def inspect_source(self, src_creds: AccountCredentials) -> MailboxSummary:
        """Inspects source account and outputs formatted terminal summary."""
        console.print(f"[bold cyan]🔍 Inspecting Source Mailbox:[/bold cyan] [yellow]{src_creds.username}[/yellow] ({src_creds.host})")

        with IMAPClientWrapper(src_creds) as src_client:
            summary = self.inspector.inspect(src_client)

            # Update Prometheus Gauges
            SOURCE_MAILBOX_SIZE_BYTES.labels(source_account=src_creds.username).set(summary.total_size_bytes)
            SOURCE_MAILBOX_MESSAGES_TOTAL.labels(source_account=src_creds.username).set(summary.total_messages)

            # Print Rich Table
            self._render_inspection_table(summary)
            return summary

    def migrate_account(
        self,
        src_creds: AccountCredentials,
        dst_creds: AccountCredentials,
        custom_folder_mapping: Optional[Dict[str, str]] = None,
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

        try:
            with IMAPClientWrapper(src_creds) as src_client, IMAPClientWrapper(dst_creds) as dst_client:
                # 1. Pre-flight inspect source
                summary = self.inspector.inspect(src_client)
                SOURCE_MAILBOX_SIZE_BYTES.labels(source_account=src_creds.username).set(summary.total_size_bytes)
                SOURCE_MAILBOX_MESSAGES_TOTAL.labels(source_account=src_creds.username).set(summary.total_messages)

                # 2. Start session in State DB for idempotency & auditing
                migration_id = self.state_db.start_migration(
                    src_creds.username, dst_creds.username, summary.total_messages
                )

                # 3. Inspect destination folder hierarchy for role mapping
                dst_folders = dst_client.client.list_folders()
                dst_canonical_map: Dict[FolderRole, str] = {}
                dest_delim = "/"

                for flags, delimiter, raw_name in dst_folders:
                    dest_delim = delimiter.decode("latin-1") if isinstance(delimiter, bytes) else str(delimiter)
                    folder_name = self.mapper.decode_folder_name(raw_name)
                    role = self.mapper.identify_role(folder_name, flags)
                    if role != FolderRole.CUSTOM and role not in dst_canonical_map:
                        dst_canonical_map[role] = folder_name

                # 4. Migrate each non-excluded selectable folder
                migrated_msgs_counter = 0
                total_target_msgs = summary.total_messages or 1

                for folder in summary.folders:
                    if folder.is_excluded or not folder.is_selectable:
                        continue

                    # Map target name
                    target_name = self.mapper.map_folder_name(
                        source_folder=folder.name,
                        source_role=folder.role,
                        source_delim=folder.delimiter,
                        dest_delim=dest_delim,
                        dest_canonical_map=dst_canonical_map,
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
                    )
                    total_success += s_count
                    total_failed += f_count
                    total_skipped += skip_count
                    migrated_msgs_counter += (s_count + f_count + skip_count)

                ACCOUNT_PROGRESS_PERCENT.labels(
                    source_account=src_creds.username, dest_account=dst_creds.username
                ).set(100.0)

                # 5. Mark completion in State DB
                final_status = "COMPLETED" if total_failed == 0 else "PARTIAL"
                self.state_db.complete_migration(migration_id, status=final_status)

                # 6. Generate HTML and CSV audit reports
                html_report, csv_report = self.reporter.generate_reports(migration_id)

                # 7. Print summary panel
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
