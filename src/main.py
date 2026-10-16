import argparse
import sys
from rich.console import Console

from src.cli.menu import run_interactive_menu, show_banner
from src.core.models import AccountCredentials
from src.core.service import MigrationService
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import start_metrics_server

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Py-IMAP Email Migration Engine & Monitoring")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI menu")
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
    try:
        start_metrics_server(port=args.port)
        logger.info("Prometheus metrics server started", port=args.port)
    except Exception as e:
        logger.warning("Metrics server note", error=str(e))

    service = MigrationService()

    # 1. Non-interactive CLI flag: Inspect Source
    if args.inspect_source:
        if not (args.host and args.user and args.password):
            console.print("[bold red]Lỗi: Cần cung cấp đầy đủ --host, --user và --password cho --inspect-source[/bold red]")
            sys.exit(1)

        creds = AccountCredentials(
            host=args.host,
            port=993,
            ssl=True,
            username=args.user,
            password=args.password,
        )
        service.inspect_source(creds)

    # 2. Non-interactive CLI flag: Batch CSV
    elif args.csv:
        from src.cli.menu import handle_migrate_csv
        # Can run automated or interactive
        service = MigrationService()
        # Direct batch run
        from src.cli.menu import handle_migrate_csv
        handle_migrate_csv(service)

    # 3. Non-interactive CLI flag: Simulation mode
    elif args.simulate:
        from src.main_simulation import run_simulation_loop
        run_simulation_loop(logger)

    # 4. Default: Launch Interactive Menu
    else:
        show_banner(metrics_port=args.port)
        run_interactive_menu(service, logger)


if __name__ == "__main__":
    main()
