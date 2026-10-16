import argparse
import csv
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from src.core.models import AccountCredentials
from src.core.service import MigrationService
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import start_metrics_server

console = Console()


def run_csv_batch(csv_path: str, service: MigrationService):
    """Processes batch migration from a CSV file."""
    path = Path(csv_path)
    if not path.exists():
        console.print(f"[bold red]Error: CSV file not found at {csv_path}[/bold red]")
        sys.exit(1)

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        accounts = list(reader)

    console.print(f"[bold green]Loaded {len(accounts)} account(s) for migration.[/bold green]")

    for idx, row in enumerate(accounts, 1):
        console.print(f"\n[bold yellow]=== Processing Account [{idx}/{len(accounts)}] ===[/bold yellow]")
        src_creds = AccountCredentials(
            host=row["source_host"].strip(),
            port=int(row.get("source_port", 993)),
            ssl=str(row.get("source_ssl", "true")).lower() in ("true", "1"),
            username=row["source_user"].strip(),
            password=row["source_password"].strip(),
        )
        dst_creds = AccountCredentials(
            host=row["dest_host"].strip(),
            port=int(row.get("dest_port", 993)),
            ssl=str(row.get("dest_ssl", "true")).lower() in ("true", "1"),
            username=row["dest_user"].strip(),
            password=row["dest_password"].strip(),
        )

        try:
            service.migrate_account(src_creds, dst_creds)
        except Exception as e:
            console.print(f"[bold red]Failed migrating {src_creds.username}: {e}[/bold red]")


def main():
    parser = argparse.ArgumentParser(description="Py-IMAP Email Migration Engine & Monitoring")
    parser.add_argument("--simulate", action="store_true", help="Run simulated migration to test Prometheus & Grafana")
    parser.add_argument("--inspect-source", action="store_true", help="Inspect source mailbox size, quota, and folders")
    parser.add_argument("--csv", type=str, help="Path to accounts.csv for batch migration")
    parser.add_argument("--host", type=str, help="IMAP Source Host for single inspection/migration")
    parser.add_argument("--user", type=str, help="IMAP Source Username")
    parser.add_argument("--password", type=str, help="IMAP Source Password / App Password")
    parser.add_argument("--port", type=int, default=8000, help="Prometheus metrics exporter port")
    args = parser.parse_args()

    logger = setup_logging()

    # Always start Prometheus metrics exporter
    start_metrics_server(port=args.port)
    logger.info("Prometheus metrics server started", port=args.port)

    service = MigrationService()

    if args.inspect_source:
        if not (args.host and args.user and args.password):
            console.print("[bold red]Error: --host, --user, and --password are required for --inspect-source[/bold red]")
            sys.exit(1)

        creds = AccountCredentials(
            host=args.host,
            port=993,
            ssl=True,
            username=args.user,
            password=args.password,
        )
        service.inspect_source(creds)

    elif args.csv:
        run_csv_batch(args.csv, service)

    elif args.simulate or len(sys.argv) == 1:
        # Default behavior: run simulation for live Grafana demonstration
        from src.main_simulation import run_simulation_loop
        run_simulation_loop(logger)


if __name__ == "__main__":
    main()
