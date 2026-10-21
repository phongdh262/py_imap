import argparse
import sys
from rich.console import Console

from src.core.timezone import init_timezone
from src.cli.menu import run_interactive_menu, show_banner
from src.core.models import AccountCredentials
from src.core.service import MigrationService
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import start_metrics_server

console = Console()


def main():
    init_timezone()
    parser = argparse.ArgumentParser(description="Py-IMAP Email Migration Engine & Monitoring")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI menu")
    parser.add_argument("--simulate", action="store_true", help="Run simulated migration to test Prometheus & Grafana")
    parser.add_argument("--inspect-source", action="store_true", help="Inspect source mailbox size, quota, and folders")
    parser.add_argument("--csv", type=str, help="Path to accounts.csv for batch migration")
    parser.add_argument("--host", type=str, help="IMAP Source Host for single inspection/migration")
    parser.add_argument("--user", type=str, help="IMAP Source Username")
    parser.add_argument("--password", type=str, help="IMAP Source Password / App Password")
    parser.add_argument("--check-password", action="store_true", help="Quickly check app password for single account")
    parser.add_argument("--check-csv", type=str, help="Check app passwords in batch from CSV")
    parser.add_argument("--web", action="store_true", help="Launch Web Admin Control Panel (FastAPI)")
    parser.add_argument("--web-port", type=int, default=8080, help="Web Admin Control Panel port")
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

    # 0. Web Admin Control Panel
    if args.web:
        from src.web.server import start_web_server
        console.print(f"[bold green]🚀 Khởi chạy Py-IMAP Web Admin Panel tại: http://0.0.0.0:{args.web_port}[/bold green]")
        start_web_server(host="0.0.0.0", port=args.web_port)

    # 1. Non-interactive CLI flag: Check single password
    elif args.check_password:
        if not (args.host and args.user and args.password):
            console.print("[bold red]Lỗi: Cần cung cấp đầy đủ --host, --user và --password cho --check-password[/bold red]")
            sys.exit(1)
        from src.core.auth_checker import AuthChecker
        checker = AuthChecker()
        creds = AccountCredentials(host=args.host, port=993, ssl=True, username=args.user, password=args.password)
        res = checker.check_single(creds)
        checker.render_results_table([res])

    # 2. Non-interactive CLI flag: Check batch CSV
    elif args.check_csv:
        from src.core.auth_checker import AuthChecker
        checker = AuthChecker()
        checker.check_from_csv(args.check_csv)

    # 3. Non-interactive CLI flag: Inspect Source
    elif args.inspect_source:
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
